from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import stripe
from dotenv import load_dotenv
import firebase_service
from firebase_admin import auth
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes
app.secret_key = os.getenv('SECRET_KEY', 'default_secret')

# Stripe Setup
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/api/verify_token', methods=['POST'])
def verify_token():
    token = request.json.get('token')
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name')
        
        # Sync user to Firestore
        firebase_service.create_or_update_user(uid, email, name)
        
        return jsonify({'success': True, 'uid': uid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

@app.route('/api/wallet/balance', methods=['GET'])
def get_balance():
    uid = request.args.get('uid')
    if not uid: return jsonify({'error': 'UID required'}), 400
    balance = firebase_service.get_user_balance(uid)
    return jsonify({'balance': balance})

@app.route('/api/check-in', methods=['POST'])
def check_in():
    data = request.json
    uid = data.get('uid')
    vehicle = data.get('vehicle')
    if not uid or not vehicle:
        return jsonify({'success': False, 'message': 'Missing data'}), 400
        
    result = firebase_service.check_in_vehicle(uid, vehicle)
    return jsonify(result)

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.json
        amount = data.get('amount', 100)
        uid = data.get('uid')
        email = data.get('email') # Get email
        
        # Sanitize metadata (ensure strings)
        safe_uid = str(uid).strip() if uid else "unknown"
        safe_amount = str(amount).strip()

        # Create Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=email,
            locale='en', # Force English to avoid browser-locale crashes
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': 'Wallet Top-up',
                    },
                    'unit_amount': int(float(amount) * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={
                'uid': safe_uid,
                'amount': safe_amount
            },
            success_url='https://parkease-21eda.web.app/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://parkease-21eda.web.app/?canceled=true',
        )
        return jsonify({'url': session.url, 'id': session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 403

@app.route('/api/payment/confirm-session', methods=['POST'])
def confirm_session():
    data = request.json
    session_id = data.get('session_id')
    
    try:
        # Verify session with Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
             # Retrieve secure data from metadata
             uid = session.metadata.get('uid')
             amount = session.metadata.get('amount')
             
             new_bal = firebase_service.add_funds(uid, float(amount))
             return jsonify({'success': True, 'new_balance': new_bal})
        return jsonify({'success': False, 'message': 'Payment not paid'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    uid = request.args.get('uid')
    if not uid: return jsonify({'error': 'UID required'}), 400
    
    transactions = firebase_service.get_user_transactions(uid)
    return jsonify({'history': transactions})

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

