import os
import re
import hashlib
import logging
from functools import wraps
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import stripe
from dotenv import load_dotenv
import requests
import xml.etree.ElementTree as ET
from uuid import uuid4
from supabase import create_client

# Configuration initiale
load_dotenv()
app = Flask(__name__, static_folder='dist', static_url_path='/')

# Configuration CORS simplifiée
CORS(app,
     origins=["https://shay-b.netlify.app"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True)

# Configuration Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-10-16'

# Vérification des variables d'environnement
required_env_vars = ['STRIPE_SECRET_KEY', 'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'MONDIALRELAY_BRAND_ID', 'MONDIALRELAY_SECURITY_KEY']
for var in required_env_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"Variable d'environnement manquante : {var}")

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Clients externes
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

class StripeService:
    @staticmethod
    def create_individual_account(data):
        """Crée un compte Stripe pour un particulier avec validation robuste"""
        validation_rules = {
            'first_name': (str, lambda v: len(v) >= 2),
            'last_name': (str, lambda v: len(v) >= 2),
            'email': (str, lambda v: re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v)),
            'phone': (str, lambda v: re.match(r"^\+?[0-9\s]{10,15}$", v)),
            'address_line1': (str, lambda v: len(v) >= 5),
            'address_city': (str, lambda v: len(v) >= 2),
            'address_postal_code': (str, lambda v: re.match(r"^[0-9]{5}$", v)),
            'iban': (str, lambda v: re.match(r"^FR[a-zA-Z0-9]{23}$", v.replace(" ", "")))
        }

        for field, (type_check, validator) in validation_rules.items():
            value = data.get(field)
            if not value or not isinstance(value, type_check) or not validator(value):
                raise ValueError(f"Champ invalide : {field}")

        return stripe.Account.create(
            type="custom",
            email=data['email'],
            country="FR",
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            business_type="individual",
            individual={
                "first_name": data['first_name'],
                "last_name": data['last_name'],
                "phone": data['phone'],
                "address": {
                    "line1": data['address_line1'],
                    "city": data['address_city'],
                    "postal_code": data['address_postal_code'],
                    "country": "FR"
                }
            },
            external_account={
                "object": "bank_account",
                "country": "FR",
                "currency": "eur",
                "account_number": data['iban'].replace(" ", "")
            },
            tos_acceptance={
                "date": int(datetime.now().timestamp()),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )

# Middleware d'authentification
def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authentification requise"}), 401
            
        try:
            user = supabase.auth.get_user(auth_header.split()[1])
            request.user = user
        except Exception as e:
            logger.error(f"Erreur d'authentification : {e}")
            return jsonify({"error": "Token invalide"}), 401
            
        return f(*args, **kwargs)
    return decorated

# Gestion centralisée des erreurs Stripe
@app.errorhandler(stripe.error.StripeError)
def handle_stripe_error(e):
    logger.error(f"Erreur Stripe : {e.user_message} ({e.code})")
    return jsonify({
        "error": e.user_message,
        "code": e.code,
        "type": e.__class__.__name__
    }), 400

@app.route('/api/accounts', methods=['POST'])
@auth_required
def create_stripe_account():
    try:
        data = request.get_json()
        account = StripeService.create_individual_account(data)
        return jsonify({"id": account.id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/accounts/<account_id>/status', methods=['GET'])
def get_account_status(account_id):
    try:
        account = stripe.Account.retrieve(account_id)
        return jsonify({
            "is_verified": account.charges_enabled and account.payouts_enabled,
            "requirements": account.requirements
        })
    except stripe.error.InvalidRequestError:
        return jsonify({"error": "Compte invalide"}), 404

@app.route('/api/checkout-sessions', methods=['POST'])
@auth_required
def create_checkout_session():
    data = request.get_json()
    
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': data.get('product_name', 'Produit Shay')},
                'unit_amount': int(data['amount'] * 100)
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=f"{os.getenv('FRONTEND_URL')}/success",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/cancel",
        payment_intent_data={
            'transfer_data': {'destination': data['stripe_account_id']}
        },
        metadata={'user_id': request.user.id}
    )
    
    return jsonify({'url': session.url})

@app.route('/api/relay-points', methods=['POST'])
def get_relay_points():
    try:
        postal_code = request.json['postal_code']
        security_code = hashlib.md5(
            f"{os.getenv('MONDIALRELAY_BRAND_ID')}{postal_code}{os.getenv('MONDIALRELAY_SECURITY_KEY')}".encode()
        ).hexdigest().upper()

        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <WSI4_PointRelais_Recherche xmlns="http://www.mondialrelay.fr/webservice/">
                    <Enseigne>{os.getenv('MONDIALRELAY_BRAND_ID')}</Enseigne>
                    <Pays>FR</Pays>
                    <CP>{postal_code}</CP>
                    <NombreResultats>20</NombreResultats>
                    <Security>{security_code}</Security>
                </WSI4_PointRelais_Recherche>
            </soap:Body>
        </soap:Envelope>"""

        response = requests.post(
            "https://api.mondialrelay.com/Web_Services.asmx",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'}
        )
        
        # Traitement de la réponse XML...
        return jsonify({"points": processed_points})
        
    except Exception as e:
        logger.error(f"Erreur Mondial Relay : {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/boost', methods=['POST'])
@auth_required
def boost_product():
    data = request.get_json()
    
    # Vérification propriété produit
    product = supabase.table("products").select("*").eq("id", data['product_id']).single().execute()
    if product['user_id'] != request.user.id:
        return jsonify({"error": "Non autorisé"}), 403
    
    # Création session de paiement...
    return jsonify({"session_url": session.url})

# Serveur de fichiers statiques
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path) if os.path.exists(f"{app.static_folder}/{path}") else send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('DEBUG', 'false').lower() == 'true')
