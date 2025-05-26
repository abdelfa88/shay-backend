import os
import hashlib
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import stripe
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import requests
from supabase import create_client

# Configuration initiale
load_dotenv()
app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app, origins=["https://shay-b.netlify.app"], supports_credentials=True)

# Configuration Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-10-16'

# Clients externes
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Helpers
def calculate_commission(amount):
    return int(amount * 0.08) + 70  # 8% + 0.70€

# Routes Stripe
@app.route('/api/create-stripe-account', methods=['POST'])
def create_stripe_account():
    try:
        data = request.get_json()
        
        required_fields = [
            'first_name', 'last_name', 'email', 'phone', 'user_id',
            'dob_day', 'dob_month', 'dob_year', 'address_line1',
            'address_city', 'address_postal_code', 'iban'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing field: {field}"}), 400

        account = stripe.Account.create(
            type="custom",
            country="FR",
            email=data['email'],
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            individual={
                "first_name": data['first_name'],
                "last_name": data['last_name'],
                "phone": data['phone'],
                "dob": {
                    "day": int(data['dob_day']),
                    "month": int(data['dob_month']),
                    "year": int(data['dob_year'])
                },
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
                "date": int(time.time()),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )

        # Enregistrement Supabase
        supabase.table('profiles').update({
            'stripe_account_id': account.id,
            'stripe_verified': False
        }).eq('user_id', data['user_id']).execute()

        return jsonify({"id": account.id})

    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@app.route('/api/create-stripe-account-token', methods=['POST'])
def create_stripe_account_token():
    try:
        data = request.get_json()
        
        account = stripe.Account.create(
            type="custom",
            country="FR",
            account_token=data['account_token'],
            business_profile={"mcc": "5734"},
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            }
        )
        
        supabase.table('profiles').update({
            'stripe_account_id': account.id,
            'stripe_verified': False
        }).eq('user_id', data['user_id']).execute()

        return jsonify({"id": account.id})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        account_id = request.form['account_id']
        purpose = request.form.get('purpose', 'identity_document')

        stripe_file = stripe.File.create(
            purpose=purpose,
            file={
                'data': file.read(),
                'name': file.filename,
                'content_type': file.content_type
            },
            stripe_account=account_id
        )
        
        return jsonify({"id": stripe_file.id})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/check-stripe-status', methods=['POST'])
def check_stripe_status():
    try:
        data = request.get_json()
        account = stripe.Account.retrieve(data['account_id'])
        
        verified = account.charges_enabled and account.payouts_enabled
        supabase.table('profiles').update({'stripe_verified': verified}).eq('stripe_account_id', data['account_id']).execute()
        
        return jsonify({
            "verified": verified,
            "requirements": account.requirements.currently_due
        })
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.get_json()
        commission = calculate_commission(data['amount'])
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': data['product_name']},
                    'unit_amount': data['amount']
                },
                'quantity': 1,
            }],
            mode='payment',
            payment_intent_data={
                'transfer_data': {'destination': data['stripe_account_id']},
                'application_fee_amount': commission
            },
            success_url=f"{os.getenv('FRONTEND_URL')}/success",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/cancel"
        )
        return jsonify({'url': session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Webhook Stripe
@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
        
        if event['type'] == 'account.updated':
            account = event['data']['object']
            supabase.table('profiles').update({
                'stripe_verified': account.charges_enabled and account.payouts_enabled
            }).eq('stripe_account_id', account.id).execute()
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Routes Mondial Relay
@app.route('/api/relay-points', methods=['POST'])
def get_relay_points():
    try:
        postal_code = request.json['postalCode']
        security_code = hashlib.md5(
            f"{os.getenv('MONDIALRELAY_BRAND_ID')}{postal_code}{os.getenv('MONDIALRELAY_SECURITY_KEY')}".encode()
        ).hexdigest().upper()

        soap_request = f"""<?xml version="1.0"?>
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
            headers={'Content-Type': 'text/xml'}
        )
        
        # Traitement réponse XML (similaire à votre implémentation existante)
        return jsonify({"points": process_xml_response(response.content)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serveur de fichiers
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path) if os.path.exists(f"{app.static_folder}/{path}") else send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
