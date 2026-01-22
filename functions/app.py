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

@app.route('/api/payment/create-intent', methods=['POST'])
def create_payment():
    try:
        data = request.json
        amount = data.get('amount', 500) # Default 500 INR
        
        intent = stripe.PaymentIntent.create(
            amount=amount * 100, # cents/paisa
            currency='inr',
            automatic_payment_methods={'enabled': True},
        )
        return jsonify({
            'clientSecret': intent['client_secret']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 403

@app.route('/api/payment/confirm', methods=['POST'])
def confirm_payment():
    # In a real app, use Webhooks. For prototype, we trust the client call for now 
    # BUT strictly speaking we should verify the intent status here or use webhooks.
    # For simplicity/speed in this demo, we'll assume the client calls this after successful payment
    # with the payment_intent_id to verify.
    
    data = request.json
    uid = data.get('uid')
    amount = data.get('amount')
    payment_intent_id = data.get('payment_intent_id')
    
    if not uid or not amount:
        return jsonify({'success': False}), 400

    # Retrieve intent to verify
    try:
        # BYPASS for Demo/Mock payments
        if payment_intent_id.startswith("pi_MOCK"):
             new_bal = firebase_service.add_funds(uid, amount)
             return jsonify({'success': True, 'new_balance': new_bal})

        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        if intent.status == 'succeeded':
            new_bal = firebase_service.add_funds(uid, amount)
            return jsonify({'success': True, 'new_balance': new_bal})
        else:
             return jsonify({'success': False, 'message': 'Payment not successful'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

