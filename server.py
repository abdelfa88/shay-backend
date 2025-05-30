import os
import json
import time
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import stripe
from dotenv import load_dotenv
import tempfile

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = '2023-10-16'

app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app, resources={r"/*": {"origins": "*"}})

# ========================================================
# STRIPE ACCOUNT CREATION (FRANCE COMPATIBLE)
# ========================================================
@app.route('/api/create-stripe-account', methods=['POST', 'OPTIONS'])
def create_stripe_account_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        
        # Validate required fields for France
        required_fields = ['first_name', 'last_name', 'email', 'phone', 
                          'dob_day', 'dob_month', 'dob_year', 
                          'address_line1', 'address_city', 'address_postal_code', 'iban']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Champ obligatoire manquant: {field}"}), 400
        
        # Create account with France-specific defaults
        account = stripe.Account.create(
            type="custom",
            email=data['email'],
            country=data.get('country', 'FR'),
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            business_type=data.get('business_type', 'individual'),
            business_profile={
                "name": f"{data['first_name']} {data['last_name']}",
                "url": data.get('website', 'https://shaybeauty.fr'),
                "mcc": data.get('business_profile_mcc', '7230')
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
                    "country": data.get('address_country', 'FR')
                },
                "verification": {
                    "document": {
                        "front": None
                    }
                }
            },
            external_account={
                "object": "bank_account",
                "country": 'FR',
                "currency": data.get('currency', 'eur'),
                "account_number": data['iban'].replace(" ", "")
            },
            settings={
                "payouts": {
                    "schedule": {
                        "interval": "manual"
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
        
    except stripe.error.StripeError as e:
        return jsonify({
            "error": "Stripe error",
            "details": e.user_message if hasattr(e, 'user_message') else str(e)
        }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================================================
# DOCUMENT UPLOAD (FRANCE COMPATIBLE)
# ========================================================
@app.route('/api/upload-document', methods=['POST', 'OPTIONS'])
def upload_document_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier fourni"}), 400
            
        file = request.files['file']
        purpose = request.form.get('purpose')
        account_id = request.form.get('account_id')
        
        if not file or not purpose or not account_id:
            return jsonify({"error": "Paramètres manquants"}), 400
        
        # Upload file to Stripe
        file_upload = stripe.File.create(
            purpose=purpose,
            file=file,
            stripe_account=account_id
        )
        
        # Handle identity document specifically
        if purpose == 'identity_document':
            try:
                # FRANCE: Use token method for account updates
                token = stripe.Token.create(
                    account={
                        "individual": {
                            "verification": {
                                "document": {
                                    "front": file_upload.id
                                }
                            }
                        }
                    },
                    stripe_account=account_id
                )

                # Update account with token
                stripe.Account.modify(
                    account_id,
                    account_token=token.id
                )
            except stripe.error.StripeError as e:
                return jsonify({
                    "warning": "Document uploaded but account not updated",
                    "details": e.user_message
                }), 200
        
        return jsonify({"id": file_upload.id})
            
    except stripe.error.StripeError as e:
        return jsonify({
            "error": "Stripe error",
            "details": e.user_message if hasattr(e, 'user_message') else str(e)
        }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================================================
# CHECK ACCOUNT STATUS (FRANCE COMPATIBLE)
# ========================================================
@app.route('/api/check-stripe-status', methods=['POST', 'OPTIONS'])
def check_stripe_status_route():
    if request.method == 'OPTIONS':
        return handle_cors()
    
    try:
        data = request.json
        account_id = data.get('account_id')
        
        if not account_id:
            return jsonify({"error": "Account ID manquant"}), 400
        
        account = stripe.Account.retrieve(account_id)
        requirements = account.requirements
        
        # France-specific status checks
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
        return jsonify({
            "error": "Stripe error",
            "details": e.user_message
        }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================================================
# HELPER FUNCTIONS
# ========================================================
def handle_cors():
    response = jsonify({"message": "CORS preflight"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
