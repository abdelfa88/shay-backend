import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import stripe
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Initialize Stripe with API key from .env
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-10-16'

# Verify API key
if not stripe.api_key or not stripe.api_key.startswith('sk_'):
    print("❌ Error: Invalid or missing Stripe API key.")
else:
    print(f"✅ Stripe API key detected: {stripe.api_key[:4]}************")

# Initialize Flask app
app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app,
     resources={r"/*": {"origins": ["https://shay-b.netlify.app"]}},
     supports_credentials=True,
     expose_headers=["Content-Type", "Authorization"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])
# CORS Headers ajoutés à chaque réponse
@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "https://shay-b.netlify.app")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

@app.route('/api/upload-document', methods=['OPTIONS'])
def upload_document_options():
    response = jsonify({'message': 'Preflight OK'})
    response.headers.add("Access-Control-Allow-Origin", "https://shay-b.netlify.app")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response
    
@app.route('/', methods=['POST'])
def handle_stripe_action():
    try:
        data = request.json
        if not data or 'action' not in data:
            return jsonify({"error": "Missing 'action' field"}), 400

        action = data['action']

        if action == 'create-stripe-account-with-token':
            return create_stripe_account_with_token(data)
        elif action == 'check-stripe-status':
            return check_stripe_status()
        elif action == 'upload-document':
            return upload_document()
        else:
            return jsonify({"error": f"Unknown action '{action}'"}), 400

    except Exception as e:
        print(f"❌ Error in handle_stripe_action: {e}")
        return jsonify({"error": str(e)}), 500

def create_stripe_account_with_token(data):
    try:
        account_token = data.get('account_token')
        email = data.get('email')
        iban = data.get('iban')
        website = data.get('website')

        if not account_token:
            return jsonify({"error": "Missing account_token"}), 400

        account = stripe.Account.create(
            type="custom",
            country="FR",
            email=email,
            account_token=account_token,
            business_profile={
                "url": website or "https://shay-b.netlify.app",
                "mcc": "5734"  # Secteur d’activité : 5734 = "Computer Software Stores", change si besoin
            },
            external_account={
                "object": "bank_account",
                "country": "FR",
                "currency": "eur",
                "account_number": iban.replace(" ", "")
            },
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            settings={
                "payouts": {
                    "schedule": {
                        "interval": "manual"
                    }
                },
                "payments": {
                    "statement_descriptor": "SHAY BEAUTY"
                }
            }
            # ❌ Ne surtout pas inclure `tos_acceptance` ici avec un token
        )

        return jsonify({"id": account.id})

    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500
# --- Legacy API endpoints ---
@app.route('/api/create-stripe-account', methods=['POST'])
def create_stripe_account():
    try:
        data = request.json
        required_fields = ['first_name', 'last_name', 'email', 'phone',
                           'dob_day', 'dob_month', 'dob_year',
                           'address_line1', 'address_city', 'address_postal_code', 'iban']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        account = stripe.Account.create(
            type="custom",
            email=data['email'],
            country="FR",
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            business_type=data.get('business_type', 'individual'),
            business_profile={
                "name": f"{data['first_name']} {data['last_name']}",
                "url": data.get('website', 'https://example.com')
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
            settings={
                "payouts": {
                    "schedule": {
                        "interval": "manual"
                    }
                },
                "payments": {
                    "statement_descriptor": "SHAY BEAUTY"
                }
            },
            tos_acceptance={
                "date": int(data.get('tos_date', int(time.time()))),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )
        return jsonify({"id": account.id})
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Error creating Stripe account: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-custom-account', methods=['POST'])
def create_custom_account():
    try:
        account = stripe.Account.create(
            type="custom",
            country="FR",
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            business_type="individual",
            tos_acceptance={
                "date": int(time.time()),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )
        return jsonify({"id": account.id})
    except Exception as e:
        print(f"Error creating custom Stripe account: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-stripe-status', methods=['OPTIONS'])
def check_stripe_status_options():
    response = jsonify({'message': 'Preflight OK'})
    response.headers.add("Access-Control-Allow-Origin", "https://shay-b.netlify.app")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response
    
@app.route('/api/check-stripe-status', methods=['POST'])
def check_stripe_status():
    try:
        data = request.json
        account_id = data.get('account_id')
        if not account_id:
            return jsonify({"error": "Missing account_id parameter"}), 400

        account = stripe.Account.retrieve(account_id)
        status = {
            "isVerified": account.charges_enabled and account.payouts_enabled,
            "isRestricted": account.requirements.disabled_reason is not None,
            "requiresInfo": len(account.requirements.currently_due) > 0,
            "pendingRequirements": account.requirements.currently_due,
            "currentDeadline": account.requirements.current_deadline
        }
        return jsonify(status)
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return jsonify({
            "isVerified": True,
            "isRestricted": False,
            "requiresInfo": False,
            "pendingRequirements": [],
            "currentDeadline": None
        })
    except Exception as e:
        print(f"Error checking Stripe status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        purpose = request.form.get('purpose')
        account_id = request.form.get('account_id')

        if not file or not purpose or not account_id:
            return jsonify({"error": "Missing required parameters"}), 400

        file_data = file.read()
        file_upload = stripe.File.create(
            purpose=purpose,
            file={
                'data': file_data,
                'name': file.filename,
                'type': file.content_type
            },
            stripe_account=account_id
        )
        return jsonify({"id": file_upload.id})
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return jsonify({"id": f"file_simulated_{int(time.time())}"})
    except Exception as e:
        print(f"Error uploading document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.json
        amount = data.get('amount')  # En centimes
        seller_account = data.get('stripe_account_id')

        if not amount or not seller_account:
            return jsonify({"error": "amount and stripe_account_id are required"}), 400

        # Paiement 100% reversé au vendeur, pas de frais
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': 'Produit Shay'},
                    'unit_amount': int(amount),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://shay-b.netlify.app/success',
            cancel_url='https://shay-b.netlify.app/cancel',
            payment_intent_data={
                'transfer_data': {
                    'destination': seller_account
                }
            }
        )

        return jsonify({'url': session.url})

    except Exception as e:
        print(f"❌ Error creating checkout session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-appointment-checkout', methods=['POST'])
def create_appointment_checkout():
    try:
        data = request.json
        amount = data.get('amount')  # en centimes
        seller_account = data.get('stripe_account_id')

        if not amount or not seller_account:
            return jsonify({"error": "amount and stripe_account_id are required"}), 400

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': 'Acompte réservation'},
                    'unit_amount': int(amount),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://shay-b.netlify.app/success',
            cancel_url='https://shay-b.netlify.app/cancel',
            payment_intent_data={
                'transfer_data': {
                    'destination': seller_account
                }
            },
            stripe_account=None  # ne rien forcer ici
        )

        return jsonify({'url': session.url})

    except Exception as e:
        print(f"❌ Error creating appointment checkout session: {e}")
        return jsonify({"error": str(e)}), 500

import xml.etree.ElementTree as ET
import requests

@app.route('/api/get-relay-points', methods=['POST'])
def get_relay_points():
    try:
        data = request.json
        postal_code = data.get("postalCode")

        if not postal_code:
            return jsonify({"error": "Code postal requis"}), 400

        payload = {
            "Enseigne": os.getenv("MONDIALRELAY_BRAND_ID"),
            "Pays": "FR",
            "CP": postal_code
        }

        response = requests.post(
    "https://connect-api.mondialrelay.com/api/Shipment/GetPointsRelais",
    json=payload,
    auth=(
        os.getenv("MONDIALRELAY_LOGIN"),
        os.getenv("MONDIALRELAY_PASSWORD")
    )
)

if response.status_code != 200:
    raise Exception(f"Erreur API Mondial Relay : {response.status_code}")

print("🔵 Réponse Mondial Relay :", response.text)  # juste pour debug

root = ET.fromstring(response.text)

        relay_points = []
        for point in root.findall(".//PointRelais_Details"):
            relay_points.append({
                "id": point.findtext("Num", default=""),
                "name": point.findtext("LgAdr1", default=""),
                "address": point.findtext("LgAdr3", default=""),
                "postalCode": point.findtext("CP", default=""),
                "city": point.findtext("Ville", default=""),
                "distance": 0,
                "openingHours": f"{point.findtext('Horaires_Lundi', '')}, {point.findtext('Horaires_Samedi', '')}"
            })

        return jsonify(relay_points)

    except Exception as e:
        print(f"❌ Error fetching real Mondial Relay points: {e}")
        return jsonify({"error": str(e)}), 500
        
# Serve frontend
@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve(path):
    if path and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# Run server
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"✅ Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
