import os
import time
import stripe
import requests
import xml.etree.ElementTree as ET
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from uuid import uuid4
from supabase import create_client

# Charger les variables d’environnement
load_dotenv()

# Initialiser Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe.api_version = "2023-10-16"

# Initialiser Supabase
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Configurer Flask
app = Flask(__name__, static_folder="dist", static_url_path="/")
CORS(app,
     origins=["https://shay-b.netlify.app"],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "https://shay-b.netlify.app"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# ✅ Créer un compte Stripe complet
@app.route("/api/create-stripe-account", methods=["POST"])
def create_stripe_account():
    try:
        data = request.json
        required_fields = [
            "first_name", "last_name", "email", "phone",
            "dob_day", "dob_month", "dob_year",
            "address_line1", "address_city", "address_postal_code", "iban"
        ]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing field: {field}"}), 400

        account = stripe.Account.create(
            type="custom",
            country="FR",
            email=data["email"],
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            individual={
                "first_name": data["first_name"],
                "last_name": data["last_name"],
                "phone": data["phone"],
                "dob": {
                    "day": int(data["dob_day"]),
                    "month": int(data["dob_month"]),
                    "year": int(data["dob_year"])
                },
                "address": {
                    "line1": data["address_line1"],
                    "city": data["address_city"],
                    "postal_code": data["address_postal_code"],
                    "country": "FR"
                }
            },
            external_account={
                "object": "bank_account",
                "country": "FR",
                "currency": "eur",
                "account_number": data["iban"].replace(" ", "")
            },
            settings={
                "payouts": {"schedule": {"interval": "manual"}},
                "payments": {"statement_descriptor": "SHAY BEAUTY"}
            },
            tos_acceptance={
                "date": int(data.get("tos_date", time.time())),
                "ip": request.remote_addr,
                "service_agreement": "full"
            }
        )
        return jsonify({"id": account.id})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Vérifier le statut Stripe
@app.route("/api/check-stripe-status", methods=["POST"])
def check_stripe_status():
    try:
        data = request.json
        account_id = data.get("account_id")
        if not account_id:
            return jsonify({"error": "Missing account_id"}), 400

        account = stripe.Account.retrieve(account_id)

        has_active_transfers = account.capabilities.get("transfers") == "active"
        has_no_pending = not account.requirements.get("currently_due")
        has_no_disabled_reason = account.requirements.get("disabled_reason") is None

        return jsonify({
            "isVerified": has_active_transfers and has_no_pending and has_no_disabled_reason,
            "isRestricted": not has_no_disabled_reason,
            "requiresInfo": not has_no_pending,
            "pendingRequirements": account.requirements.get("currently_due", []),
            "currentDeadline": account.requirements.get("current_deadline")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Upload de document
@app.route("/api/upload-document", methods=["POST"])
def upload_document():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        purpose = request.form.get("purpose")
        account_id = request.form.get("account_id")

        if not file or not purpose or not account_id:
            return jsonify({"error": "Missing parameters"}), 400

        file_upload = stripe.File.create(
            purpose=purpose,
            file={
                "data": file.read(),
                "name": file.filename,
                "type": file.content_type
            },
            stripe_account=account_id
        )
        return jsonify({"id": file_upload.id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Paiement avec reversement
@app.route("/api/create-checkout-session", methods=["POST"])
def create_checkout_session():
    try:
        data = request.json
        amount = data.get("amount")
        seller_account = data.get("stripe_account_id")
        if not amount or not seller_account:
            return jsonify({"error": "amount and stripe_account_id required"}), 400

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": "Produit Shay"},
                    "unit_amount": int(amount),
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://shay-b.netlify.app/success",
            cancel_url="https://shay-b.netlify.app/cancel",
            payment_intent_data={
                "transfer_data": {
                    "destination": seller_account
                }
            }
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Mondial Relay
@app.route("/api/get-relay-points", methods=["POST"])
def get_relay_points():
    try:
        postal_code = request.json.get("postalCode")
        if not postal_code:
            return jsonify({"error": "postalCode manquant"}), 400

        soap_url = "https://api.mondialrelay.com/Web_Services.asmx"
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <WSI4_PointRelais_Recherche xmlns="http://www.mondialrelay.fr/webservice/">
                    <Enseigne>{os.getenv("MONDIALRELAY_BRAND_ID")}</Enseigne>
                    <Pays>FR</Pays>
                    <CP>{postal_code}</CP>
                    <NombreResultats>20</NombreResultats>
                    <Security>{os.getenv("MONDIALRELAY_SECURITY_KEY")}</Security>
                </WSI4_PointRelais_Recherche>
            </soap:Body>
        </soap:Envelope>"""

        response = requests.post(soap_url, data=soap_request, headers=headers)
        root = ET.fromstring(response.content)

        namespaces = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'mr': 'http://www.mondialrelay.fr/webservice/'
        }

        relay_points = []
        for point in root.findall(".//mr:PointRelais_Details", namespaces):
            get = lambda tag: point.findtext(f"mr:{tag}", namespaces=namespaces) or ""
            relay_points.append({
                "id": get("Num") or f"unknown-{uuid4()}",
                "name": get("LgAdr1"),
                "address": f"{get('LgAdr3')} {get('LgAdr4')}".strip(),
                "postalCode": get("CP"),
                "city": get("Ville"),
                "distance": float(get("Distance") or 0),
                "openingHours": get("Horaires_Livraison") or "Non communiqué",
                "photoUrl": ""
            })

        return jsonify({"relay_points": relay_points})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Serve frontend Vite/React
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    return send_from_directory(app.static_folder, path) if os.path.exists(f"{app.static_folder}/{path}") else send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Server running on port {port}")
    app.run(host="0.0.0.0", port=port)
