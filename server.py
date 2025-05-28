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
        elif action == 'create-checkout-session':
            return create_checkout_session(data)
        elif action == 'create-appointment-checkout':
            return create_appointment_checkout(data)
        elif action == 'create-boost-session':
            return create_boost_session(data)
        elif action == 'get-relay-points':
            return get_relay_points(data)
        elif action == 'create-shipping-label':
            return create_shipping_label(data)
        elif action == 'test':
            return jsonify({"message": "API test successful", "received": data}), 200
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
        mcc = data.get('mcc', '7230')  # Default to beauty salons
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
                "mcc": mcc
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
        
        # Force account to require document verification
        try:
            # This will trigger document verification requirements
            stripe.Account.modify(
                account.id,
                individual={
                    "verification": {
                        "document": {
                            "front": None  # This forces Stripe to require document verification
                        }
                    }
                }
            )
        except Exception as e:
            print(f"Warning: Could not force document verification: {e}")
        
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
        # ✅ Log de debug
        print("📦 Données reçues dans create_stripe_account:", data)

        # ✅ Vérifie les champs dans data["individual"] si présents
        individual = data.get('individual', {})
        missing = []

        # Champs dans "individual" ou à la racine
        for field in ['first_name', 'last_name', 'phone', 'dob_day', 'dob_month', 'dob_year']:
            if not individual.get(field) and not data.get(field):
                missing.append(field)

        # Champs obligatoires à la racine
        for field in ['email', 'iban', 'address_line1', 'address_city', 'address_postal_code']:
            if not data.get(field):
                missing.append(field)

        if missing:
            return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

        # ✅ Création du compte Stripe
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
                "mcc": data.get('business_profile_mcc', '7230')  # par défaut : beauté
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
                },
                "verification": {
                    "document": {
                        "front": None  # Forcer la vérification des documents
                    }
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
            individual={
                "verification": {
                    "document": {
                        "front": None  # This forces Stripe to require document verification
                    }
                }
            },
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
            
            # Check if verification.document.front is in the requirements
            # If not, we'll force it to be required
            document_required = 'verification.document.front' in requirements.currently_due
            
            # If document verification is not required but should be, force it
            if not document_required and not account.charges_enabled:
                try:
                    # Try to force document verification requirement
                    stripe.Account.modify(
                        account_id,
                        individual={
                            "verification": {
                                "document": {
                                    "front": None  # This forces Stripe to require document verification
                                }
                            }
                        }
                    )
                    # Retrieve the account again to get updated requirements
                    account = stripe.Account.retrieve(account_id)
                    requirements = account.requirements
                except Exception as e:
                    print(f"Warning: Could not force document verification: {e}")
            
            status = {
                "isVerified": account.charges_enabled and account.payouts_enabled,
                "isRestricted": requirements.disabled_reason is not None,
                "requiresInfo": len(requirements.currently_due) > 0,
                "pendingRequirements": requirements.currently_due,
                "currentDeadline": requirements.current_deadline,
                "capabilities": account.capabilities
            }
            
            # If the account is marked as verified but should require document verification,
            # override the status
            if status["isVerified"] and not document_required:
                # Add verification.document.front to pendingRequirements
                if 'verification.document.front' not in status["pendingRequirements"]:
                    status["pendingRequirements"].append('verification.document.front')
                
                # Set requiresInfo to true
                status["requiresInfo"] = True
                
                # Set isVerified to false until document verification is complete
                status["isVerified"] = False
            
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
            
            # Update the account to use the uploaded document
            if purpose == 'identity_document':
                try:
                    # Update the account with the document
                    stripe.Account.modify(
                        account_id,
                        individual={
                            "verification": {
                                "document": {
                                    "front": file_upload.id
                                }
                            }
                        }
                    )
                except Exception as e:
                    print(f"Warning: Could not update account with document: {e}")
            
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
        
        # Optional fields for metadata
        service_id = data.get('serviceId')
        service_title = data.get('serviceTitle')
        provider_id = data.get('providerId')
        buyer_id = data.get('buyerId')
        appointment_date = data.get('appointmentDate')
        formatted_date = data.get('formattedDate')
        deposit_amount = data.get('depositAmount')
        total_price = data.get('totalPrice')
        
        # Create a Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"Acompte pour {service_title or 'rendez-vous'}",
                            "description": f"Réservation de rendez-vous {formatted_date or ''} sur Shay Beauty",
                        },
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=data.get('successUrl', f"{request.host_url}payment/success?session_id={{CHECKOUT_SESSION_ID}}&appointment=true&date={appointment_date}&time={appointment_date}&service_id={service_id}&provider_id={provider_id}"),
            cancel_url=data.get('cancelUrl', f"{request.host_url}payment/cancel"),
            payment_intent_data={
                "application_fee_amount": 0,  # No fee for deposits
                "transfer_data": {
                    "destination": stripe_account_id,
                },
            },
            metadata={
                "type": "appointment_deposit",
                "serviceId": service_id,
                "providerId": provider_id,
                "buyerId": buyer_id,
                "appointmentDate": appointment_date,
                "depositAmount": deposit_amount,
                "totalPrice": total_price
            }
        )
        
        return jsonify({"id": session.id, "url": session.url})
    
    except Exception as e:
        print(f"Error creating appointment checkout: {e}")
        return jsonify({"error": str(e)}), 500

def create_boost_session(data):
    try:
        # Validate required fields
        required_fields = ['productId', 'duration', 'priceId']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Extract data
        product_id = data['productId']
        duration = data['duration']
        price_id = data['priceId']
        buyer_id = data.get('buyerId')
        
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

def get_relay_points(data):
    try:
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

def create_shipping_label(data):
    try:
        # Validate required fields
        required_fields = ['buyer', 'seller', 'relayPoint', 'productId']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Extract data
        buyer = data['buyer']
        seller = data['seller']
        relay_point = data['relayPoint']
        product_id = data['productId']
        order_id = data.get('orderId', str(uuid.uuid4()))
        
        # For this example, we'll return mock data
        # In a real implementation, you would call the Mondial Relay API
        mock_tracking_number = f"MR{int(time.time())}"
        mock_pdf_url = "https://example.com/shipping-label.pdf"
        
        return jsonify({
            "success": True,
            "trackingNumber": mock_tracking_number,
            "pdfUrl": mock_pdf_url
        })
    
    except Exception as e:
        print(f"Error creating shipping label: {e}")
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

@app.route('/api/create-stripe-account-token', methods=['POST'])
def create_stripe_account_token():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Aucune donnée reçue'}), 400

        # Préparer le payload requis par Stripe
        account_token = stripe.Account.create_account_token(
            account={
                'type': data.get('business_type', 'individual'),
                'individual': {
                    'first_name': data.get('first_name'),
                    'last_name': data.get('last_name'),
                    'email': data.get('email'),
                    'phone': data.get('phone'),
                    'dob': {
                        'day': int(data.get('dob_day')),
                        'month': int(data.get('dob_month')),
                        'year': int(data.get('dob_year')),
                    },
                    'address': {
                        'line1': data.get('address_line1'),
                        'city': data.get('address_city'),
                        'postal_code': data.get('address_postal_code'),
                        'country': data.get('address_country', 'FR'),
                    },
                },
                'tos_shown_and_accepted': True
            }
        )

        return jsonify({'token': account_token.id})

    except Exception as e:
        print("Erreur create-stripe-account-token:", str(e))
        return jsonify({'error': str(e)}), 500
        
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"✅ Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
    
