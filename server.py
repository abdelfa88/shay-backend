import os
import json
import time
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import stripe
from dotenv import load_dotenv
import requests
from werkzeug.utils import secure_filename
import tempfile

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
app = Flask(__name__, static_folder='static', static_url_path='/')
CORS(app, resources={r"/*": {"origins": "*"}})

# Mondial Relay API credentials
MONDIAL_RELAY_API_URL = 'https://connect-api.mondialrelay.com/api/Shipment'
MONDIAL_RELAY_BRAND_ID = 'CC22UCDZ'
MONDIAL_RELAY_API_LOGIN = 'CC22UCDZ@business-api.mondialrelay.com'
MONDIAL_RELAY_API_PASSWORD = '@YeVkNvuZ*py]nSB7:Dq'

# Temporary directory for file uploads
UPLOAD_FOLDER = tempfile.gettempdir()

# Main route for serving the frontend
@app.route('/')
def index():
    return render_template('index.html')

# API routes
@app.route('/api/create-stripe-account', methods=['POST'])
def create_stripe_account():
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'phone', 
                          'dob_day', 'dob_month', 'dob_year', 
                          'address_line1', 'address_city', 'address_postal_code', 'iban']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Create Stripe account
        account = stripe.Account.create(
            type="custom",
            email=data['email'],
            country="FR",
            capabilities={
                card_payments={"requested": True},
                transfers={"requested": True}
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
                "date": int(data.get('tos_date', time.time())),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )
        
        return jsonify({"id": account.id})
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return jsonify({"error": str(e), "details": e.user_message if hasattr(e, 'user_message') else None}), 400
    except Exception as e:
        print(f"Error creating Stripe account: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-stripe-account-with-token', methods=['POST'])
def create_stripe_account_with_token():
    try:
        data = request.json
        account_token = data.get('account_token')
        email = data.get('email')
        iban = data.get('iban')
        website = data.get('website')
        tos_date = data.get('tos_date', int(time.time()))
        
        if not account_token:
            return jsonify({"error": "Missing account_token parameter"}), 400
        
        if not email or not iban:
            return jsonify({"error": "Missing required parameters (email, iban)"}), 400
        
        # Create Stripe account with account token
        account = stripe.Account.create(
            type="custom",
            country="FR",
            email=email,
            account_token=account_token,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            business_profile={
                "url": website or 'https://example.com'
            },
            external_account={
                "object": "bank_account",
                "country": "FR",
                "currency": "eur",
                "account_number": iban.replace(" ", "")
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
                "date": int(tos_date),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )
        
        return jsonify({"id": account.id})
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return jsonify({
            "error": str(e),
            "details": e.user_message if hasattr(e, 'user_message') else None
        }), 400
    except Exception as e:
        print(f"Error creating Stripe account with token: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-stripe-status', methods=['POST'])
def check_stripe_status():
    try:
        data = request.json
        account_id = data.get('account_id')
        
        if not account_id:
            return jsonify({"error": "Missing account_id parameter"}), 400
        
        try:
            account = stripe.Account.retrieve(account_id)
            
            # Get detailed requirements
            requirements = account.requirements
            
            status = {
                "isVerified": account.charges_enabled and account.payouts_enabled,
                "isRestricted": requirements.disabled_reason is not None,
                "requiresInfo": len(requirements.currently_due) > 0,
                "pendingRequirements": requirements.currently_due,
                "currentDeadline": requirements.current_deadline,
                "capabilities": account.capabilities
            }
            
            return jsonify(status)
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            # Fallback to simulated status if Stripe API fails
            return jsonify({
                "isVerified": False,
                "isRestricted": False,
                "requiresInfo": True,
                "pendingRequirements": ['verification.document.front', 'business_profile.mcc'],
                "currentDeadline": None,
                "capabilities": {"card_payments": "inactive", "transfers": "inactive"}
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
        
        try:
            # Save file to temporary location
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Read the file
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            # Upload file to Stripe
            file_upload = stripe.File.create(
                purpose=purpose,
                file={
                    'data': file_data,
                    'name': filename,
                    'type': file.content_type
                },
                stripe_account=account_id
            )
            
            # Clean up temporary file
            os.remove(filepath)
            
            return jsonify({"id": file_upload.id})
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            # Clean up temporary file if it exists
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": str(e)}), 400
            
    except Exception as e:
        print(f"Error uploading document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-relay-points', methods=['POST'])
def get_relay_points():
    try:
        data = request.json
        
        # Validate required fields
        if 'postalCode' not in data:
            return jsonify({"error": "Missing postalCode parameter"}), 400
        
        postal_code = data['postalCode']
        
        # For this example, we'll return mock data
        # In a real implementation, you would call the Mondial Relay API
        mock_relay_points = [
            {
                "id": "12345",
                "name": "Tabac Presse du Centre",
                "address": "15 Rue du Commerce",
                "postalCode": postal_code,
                "city": "Paris",
                "distance": 0.5,
                "openingHours": "Lun-Sam: 9h-19h, Dim: Fermé"
            },
            {
                "id": "67890",
                "name": "Supermarché Express",
                "address": "42 Avenue de la République",
                "postalCode": postal_code,
                "city": "Paris",
                "distance": 1.2,
                "openingHours": "Lun-Dim: 8h-22h"
            },
            {
                "id": "24680",
                "name": "Librairie Moderne",
                "address": "8 Boulevard Saint-Michel",
                "postalCode": postal_code,
                "city": "Paris",
                "distance": 1.8,
                "openingHours": "Lun-Sam: 10h-20h, Dim: Fermé"
            }
        ]
        
        return jsonify({"relay_points": mock_relay_points})
    
    except Exception as e:
        print(f"Error getting relay points: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-shipping-label', methods=['POST'])
def create_shipping_label():
    try:
        data = request.json
        buyer = data.get('buyer')
        seller = data.get('seller')
        relay_point = data.get('relayPoint')
        product_id = data.get('productId')
        order_id = data.get('orderId')

        # Validate required fields
        if not buyer or not seller or not relay_point or not product_id:
            return jsonify({"error": "Missing required fields"}), 400

        # Create shipping label with Mondial Relay
        try:
            # Prepare the request payload for Mondial Relay API
            payload = {
                "Shipment": {
                    "BrandID": MONDIAL_RELAY_BRAND_ID,
                    "Expedition": {
                        "ShipperCivility": "MR",
                        "ShipperName": seller.get('fullName', 'Vendeur Shay Beauty'),
                        "ShipperAddress1": seller.get('street', 'Adresse du vendeur'),
                        "ShipperAddress2": "",
                        "ShipperZipCode": seller.get('postalCode', '75000'),
                        "ShipperCity": seller.get('city', 'Paris'),
                        "ShipperCountryISOCode": seller.get('country', 'FR'),
                        "ShipperEmail": seller.get('email', 'contact@example.com'),
                        "ShipperMobilePhone": seller.get('phone', ''),
                        "CustomerCivility": "MR",
                        "CustomerName": buyer.get('fullName'),
                        "CustomerAddress1": buyer.get('street'),
                        "CustomerAddress2": "",
                        "CustomerZipCode": buyer.get('postalCode'),
                        "CustomerCity": buyer.get('city'),
                        "CustomerCountryISOCode": buyer.get('country'),
                        "CustomerEmail": buyer.get('email', 'client@example.com'),
                        "CustomerMobilePhone": buyer.get('phone', ''),
                        "ParcelWeight": 1000, # Weight in grams (default 1kg)
                        "ParcelLength": 20, # Length in cm
                        "ParcelWidth": 20, # Width in cm
                        "ParcelHeight": 20, # Height in cm
                        "DeliveryMode": "24R", # 24R = Point Relais
                        "DeliveryRelayNumber": relay_point.get('id', ''), # Relay point ID
                        "CODAmount": 0, # Cash on delivery amount (not used)
                        "InsuranceAmount": 0, # Insurance amount (not used)
                        "InsuranceDevise": "EUR", # Insurance currency
                        "Observation": f"Commande Shay Beauty {order_id if order_id else ''}",
                        "LabelFormat": "PDF", # PDF format
                        "LabelLanguage": "FR", # French language
                        "CollectMode": "REL", # REL = Point Relais
                        "CollectRelayNumber": "", # Not used for this case
                    }
                }
            }

            # Make the API call to Mondial Relay
            response = requests.post(
                MONDIAL_RELAY_API_URL,
                json=payload,
                auth=(MONDIAL_RELAY_API_LOGIN, MONDIAL_RELAY_API_PASSWORD),
                headers={"Content-Type": "application/json"}
            )

            # Process the response
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('Shipment') and response_data['Shipment'].get('TrackingNumber'):
                    return jsonify({
                        "success": True,
                        "trackingNumber": response_data['Shipment']['TrackingNumber'],
                        "pdfUrl": response_data['Shipment'].get('LabelURL')
                    })
            
            # If we get here, something went wrong
            return jsonify({
                "success": False,
                "error": "Failed to create shipping label",
                "details": response.text
            }), 400
            
        except Exception as e:
            print(f"Error creating shipping label: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

# Webhook handler for Stripe events
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return jsonify({"error": "Invalid signature"}), 400
    
    # Handle the event
    if event['type'] == 'account.updated':
        account = event['data']['object']
        # Process account update
        print(f"Account {account.id} was updated")
        # Here you would update your database with the new account status
    
    return jsonify({"status": "success"})

# Main entry point
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
