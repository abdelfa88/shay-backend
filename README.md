# Shay Beauty - Stripe Integration with Flask

This project uses a Flask backend to handle Stripe API calls directly, without relying on Supabase Functions.

## Setup

### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Stripe API key:
```
STRIPE_SECRET_KEY=sk_live_your_stripe_key
FLASK_APP=server.py
FLASK_ENV=development
```

3. Start the Flask server:
```bash
python server.py
```

The server will run on http://localhost:5000

### Frontend Setup

1. Install Node.js dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

## API Endpoints

The Flask backend provides the following endpoints:

- `POST /api/create-stripe-account`: Creates a Stripe account
- `POST /api/check-stripe-status`: Checks the status of a Stripe account
- `POST /api/upload-document`: Uploads a document to Stripe

## Integration Flow

1. User fills out the Stripe account form in the frontend
2. Frontend sends the data to the Flask backend
3. Flask backend creates a Stripe account using the Stripe API
4. The Stripe account ID is returned to the frontend
5. Frontend updates the user's profile in Supabase with the Stripe account ID

## Security Considerations

- The Stripe secret key is only stored on the server side
- All API calls to Stripe are made from the backend
- The frontend only communicates with the backend, never directly with Stripe