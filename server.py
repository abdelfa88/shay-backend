import os
import json
import time
import uuid
from flask import Flask, request, jsonify, send_from_directory
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
app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app, resources={r"/*": {"origins": "*"}})

# Mondial Relay API credentials
MONDIAL_RELAY_API_URL = 'https://connect-api.mondialrelay.com/api/Shipment'
MONDIAL_RELAY_BRAND_ID = 'CC22UCDZ'
MONDIAL_RELAY_API_LOGIN = 'CC22UCDZ@business-api.mondialrelay.com'
MONDIAL_RELAY_API_PASSWORD = '@YeVkNvuZ*py]nSB7:Dq'

# Temporary directory for file uploads
UPLOAD_FOLDER = tempfile.gettempdir()

# Main route for handling all API requests
@app.route('/api/', methods=['POST', 'OPTIONS'])
def api_handler():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        # Parse JSON data
        data = request.json
        
        # Route to appropriate function based on action
        if 'action' not in data:
            return jsonify({"error": "No action specified"}), 400
        
        action = data['action']
        
        if action == 'create-stripe-account-with-token':
            return create_stripe_account_with_token(data)
        elif action == 'create-stripe-account':
            return create_stripe_account(data)
        elif action == 'check-stripe-status':
            return check_stripe_status(data)
        elif action == 'create-custom-account':
            return create_custom_account(data)
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400
    
    except Exception as e:
        print(f"Error in API handler: {e}")
        return jsonify({"error": str(e)}), 500

# Specific API routes
@app.route('/api/create-stripe-account', methods=['POST', 'OPTIONS'])
def create_stripe_account_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        return create_stripe_account(data)
    except Exception as e:
        print(f"Error creating Stripe account: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-stripe-status', methods=['POST', 'OPTIONS'])
def check_stripe_status_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        return check_stripe_status(data)
    except Exception as e:
        print(f"Error checking Stripe status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload-document', methods=['POST', 'OPTIONS'])
def upload_document_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        return upload_document()
    except Exception as e:
        print(f"Error uploading document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-checkout-session', methods=['POST', 'OPTIONS'])
def create_checkout_session_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        return create_checkout_session(data)
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-appointment-checkout', methods=['POST', 'OPTIONS'])
def create_appointment_checkout_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        return create_appointment_checkout(data)
    except Exception as e:
        print(f"Error creating appointment checkout: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-boost-session', methods=['POST', 'OPTIONS'])
def create_boost_session_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        return create_boost_session(data)
    except Exception as e:
        print(f"Error creating boost session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-relay-points', methods=['POST', 'OPTIONS'])
def get_relay_points_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        return get_relay_points(data)
    except Exception as e:
        print(f"Error getting relay points: {e}")
        return jsonify({"error": str(e)}), 500

# Function implementations
def create_stripe_account_with_token(data):
    try:
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
                "url": website or 'https://shaybeauty.fr',
                "mcc": "7230"  
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

def create_stripe_account(data):
    try:
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'phone', 
                          'dob_day', 'dob_month', 'dob_year', 
                          'address_line1', 'address_city', 'address_postal_code', 'iban']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Create Stripe account
        try:
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
                    "url": data.get('website', 'https://shaybeauty.fr'),
                    "mcc": data.get('business_profile_mcc', '7230')  # Default to beauty salons
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
            return jsonify({
                "error": str(e),
                "details": e.user_message if hasattr(e, 'user_message') else None
            }), 400
        
    except Exception as e:
        print(f"Error creating Stripe account: {e}")
        return jsonify({"error": str(e)}), 500

def create_custom_account(data=None):
    try:
        # Create a custom Stripe account with minimal information
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

def check_stripe_status(data):
    try:
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

def create_checkout_session(data):
    try:
        # Validate required fields
        required_fields = ['productId', 'productTitle', 'productPrice', 'sellerId', 'buyerId', 'deliveryAddress']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Extract data
        product_id = data['productId']
        product_title = data['productTitle']
        product_price = float(data['productPrice'])
        service_fee = float(data.get('serviceFee', product_price * 0.08))  # Default to 8%
        fixed_fee = float(data.get('fixedFee', 0.70))  # Default to 0.70€
        shipping_cost = float(data.get('shippingCost', 3.89))  # Default to 3.89€
        seller_id = data['sellerId']
        seller_stripe_id = data.get('sellerStripeId')
        buyer_id = data['buyerId']
        delivery_address = data['deliveryAddress']
        relay_point = data.get('relayPoint')
        use_platform_account = data.get('usePlatformAccount', False)
        
        # Calculate total
        total = product_price + service_fee + fixed_fee + shipping_cost
        total_cents = int(total * 100)
        
        # Calculate platform fee (service fee + fixed fee + shipping)
        platform_fee = int((service_fee + fixed_fee + shipping_cost) * 100)
        
        # Create line items
        line_items = [
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": product_title,
                        "description": "Achat sur Shay Beauty",
                    },
                    "unit_amount": int(product_price * 100),
                },
                "quantity": 1,
            },
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "Frais de service",
                        "description": "Frais de service Shay Beauty (8%)",
                    },
                    "unit_amount": int(service_fee * 100),
                },
                "quantity": 1,
            },
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "Frais fixes",
                        "description": "Frais fixes Shay Beauty",
                    },
                    "unit_amount": int(fixed_fee * 100),
                },
                "quantity": 1,
            },
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "Frais de livraison",
                        "description": "Livraison Mondial Relay",
                    },
                    "unit_amount": int(shipping_cost * 100),
                },
                "quantity": 1,
            }
        ]
        
        # Create session parameters
        session_params = {
            "payment_method_types": ["card"],
            "line_items": line_items,
            "mode": "payment",
            "success_url": data.get('successUrl', f"{request.host_url}payment/success?session_id={{CHECKOUT_SESSION_ID}}"),
            "cancel_url": data.get('cancelUrl', f"{request.host_url}payment/cancel"),
            "metadata": {
                "productId": product_id,
                "sellerId": seller_id,
                "buyerId": buyer_id,
                "platformFee": platform_fee / 100,  # Store in EUR for readability
                "sellerAmount": (total_cents - platform_fee) / 100,  # Store in EUR for readability
                "usePlatformAccount": "true" if use_platform_account else "false",
                "deliveryAddress": json.dumps(delivery_address),
                "relayPoint": json.dumps(relay_point) if relay_point else None,
                "shippingCost": shipping_cost
            }
        }
        
        # If seller has a Stripe account and we're not using the platform account, add transfer data
        if seller_stripe_id and not use_platform_account:
            session_params["payment_intent_data"] = {
                "application_fee_amount": platform_fee,  # Platform fee + shipping cost
                "transfer_data": {
                    "destination": seller_stripe_id,
                },
            }
        
        # Create the session
        session = stripe.checkout.Session.create(**session_params)
        
        return jsonify({"id": session.id, "url": session.url})
    
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return jsonify({"error": str(e)}), 500

def create_appointment_checkout(data):
    try:
        # Validate required fields
        required_fields = ['amount', 'stripe_account_id']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Extract data
        amount = int(data['amount'])  # Amount in cents
        stripe_account_id = data['stripe_account_id']
        
        # Create a Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": "Acompte pour rendez-vous",
                            "description": "Réservation de rendez-vous sur Shay Beauty",
                        },
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{request.host_url}payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{request.host_url}payment/cancel",
            payment_intent_data={
                "application_fee_amount": 0,  # No fee for deposits
                "transfer_data": {
                    "destination": stripe_account_id,
                },
            },
        )
        
        return jsonify({"id": session.id, "url": session.url})
    
    except Exception as e:
        print(f"Error creating appointment checkout: {e}")
        return jsonify({"error": str(e)}), 500

def create_boost_session(data):
    try:
        # Validate required fields
        required_fields = ['productId', 'duration', 'priceId', 'buyerId']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Extract data
        product_id = data['productId']
        duration = data['duration']
        price_id = data['priceId']
        buyer_id = data['buyerId']
        
        # Create a Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{request.host_url}payment/success?type=boost&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{request.host_url}payment/cancel",
            metadata={
                "productId": product_id,
                "duration": duration,
                "userId": buyer_id,
                "type": "boost"
            },
            client_reference_id=buyer_id,
        )
        
        return jsonify({"id": session.id, "url": session.url})
    
    except Exception as e:
        print(f"Error creating boost session: {e}")
        return jsonify({"error": str(e)}), 500

import hashlib
import xml.etree.ElementTree as ET

def get_relay_points():
    try:
        postal_code = request.json.get('postalCode')

        # Configuration Mondial Relay
        soap_url = "https://api.mondialrelay.com/WebService.asmx"
        headers = {'Content-Type': 'text/xml; charset=utf-8'}
        brand_id = os.getenv("MONDIALRELAY_BRAND_ID")
        private_key = os.getenv("MONDIALRELAY_SECURITY_KEY")

        # 🔐 Calcul signature
        security_code = hashlib.md5(f"{brand_id}FR{postal_code}1{private_key}".encode()).hexdigest().upper()

        # SOAP Request
        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <WSI2_PointRelais_Recherche xmlns="http://www.mondialrelay.fr/webservice/">
                    <Enseigne>{brand_id}</Enseigne>
                    <Pays>FR</Pays>
                    <CP>{postal_code}</CP>
                    <NombreResultats>5</NombreResultats>
                    <TypeActivite>1</TypeActivite>
                    <Security>{security_code}</Security>
                </WSI2_PointRelais_Recherche>
            </soap:Body>
        </soap:Envelope>"""

        # Envoi
        response = requests.post(soap_url, data=soap_request.encode('utf-8'), headers=headers)
        if response.status_code != 200:
            print("Mondial Relay response error:", response.text)
            return jsonify({'error': 'Mondial Relay API failed'}), 500

        # Parser XML
        root = ET.fromstring(response.content)
        ns = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'mr': 'http://www.mondialrelay.fr/webservice/'
        }

        relay_points = []
        for point in root.findall(".//mr:PointRelais_Details", ns):
            relay_points.append({
                "id": point.findtext('mr:Num', namespaces=ns),
                "name": point.findtext('mr:LgAdr1', namespaces=ns),
                "address": point.findtext('mr:LgAdr3', namespaces=ns),
                "postalCode": point.findtext('mr:CP', namespaces=ns),
                "city": point.findtext('mr:Ville', namespaces=ns),
                "distance": float(point.findtext('mr:Distance', namespaces=ns) or 0),
                "openingHours": point.findtext('mr:Horaires_Lundi', namespaces=ns) or 'Non communiqué',
                "photoUrl": ""
            })

        return jsonify({"relay_points": relay_points})

    except Exception as e:
        print("Erreur Mondial Relay:", e)
        return jsonify({'error': str(e)}), 500
        
        # ✅ Parse XML response
        root = ET.fromstring(response.content)
        ns = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/'}
        body = root.find('soap:Body', ns)
        result = body.find('.//{http://www.mondialrelay.fr/webservice/}WSI2_PointRelais_RechercheResult')
        parcel_list = result.find('ListePointRelais')

        relay_points = []
        if parcel_list is not None:
            for point in parcel_list.findall('PointRelais_Details'):
                relay_points.append({
                    "id": point.findtext('Num'),
                    "name": point.findtext('LgAdr1'),
                    "address": point.findtext('LgAdr2'),
                    "postalCode": point.findtext('CP'),
                    "city": point.findtext('Ville'),
                    "distance": float(point.findtext('Distance') or 0),
                    "openingHours": point.findtext('Horaires_Lundi')  # Simplifié
                })

        return jsonify({"relay_points": relay_points})

    except Exception as e:
        print("Erreur Mondial Relay:", e)
        return jsonify({"error": str(e)}), 500
        
def handle_cors():
    response = jsonify({"message": "CORS preflight request"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# Serve static files from the dist directory
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"✅ Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
