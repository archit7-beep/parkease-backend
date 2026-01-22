import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Initialize Firebase
import json

cred_path = os.getenv('FIREBASE_CREDENTIALS', 'serviceAccountKey.json')
service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')

try:
    if service_account_json:
        # Load from Env Var (Best for Render)
        cred_dict = json.loads(service_account_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully from Environment Variable.")
    elif os.path.exists(cred_path):
        # Load from File (Best for Local)
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully from File.")
    else:
        print(f"Warning: neither {cred_path} nor FIREBASE_SERVICE_ACCOUNT_JSON found. DB disabled.")
        db = None
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    db = None

def get_user_balance(uid):
    if not db: return 0.0
    user_ref = db.collection('users').document(uid)
    doc = user_ref.get()
    if doc.exists:
        return doc.to_dict().get('wallet_balance', 0.0)
    return 0.0

def create_or_update_user(uid, email, name=None):
    if not db: return
    user_ref = db.collection('users').document(uid)
    if not user_ref.get().exists:
        userData = {
            'email': email,
            'wallet_balance': 0.0,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        if name:
            userData['name'] = name
        user_ref.set(userData)

def add_funds(uid, amount):
    if not db: return False
    try:
        user_ref = db.collection('users').document(uid)
        
        # Run in transaction to ensure atomicity
        @firestore.transactional
        def update_balance_transaction(transaction, ref, val):
            snapshot = transaction.get(ref)
            new_balance = snapshot.get('wallet_balance') + val
            transaction.update(ref, {'wallet_balance': new_balance})
            return new_balance

        transaction = db.transaction()
        new_bal = update_balance_transaction(transaction, user_ref, amount)
        
        # Record transaction log
        db.collection('transactions').add({
            'uid': uid,
            'amount': amount,
            'type': 'CREDIT_TOPUP',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'description': 'Wallet top-up'
        })
        
        return new_bal
    except Exception as e:
        print(f"Transaction failed: {e}")
        return False

def check_in_vehicle(uid, vehicle_number, daily_charge=50):
    if not db: return {"success": False, "message": "Database not connected"}
    
    user_ref = db.collection('users').document(uid)
    
    # Use transaction for check-in
    @firestore.transactional
    def check_in_transaction(transaction, ref):
        snapshot_result = transaction.get(ref)
        # Handle generator return type from transaction.get()
        try:
            # If it's a generator, get the first item
            snapshot = next(snapshot_result)
        except TypeError:
            # If it's not iterable (already a snapshot), use it directly
            snapshot = snapshot_result
            
        if not snapshot.exists:
             # Auto-create if missing (Edge case fix)
             transaction.set(ref, {
                'email': 'unknown@parkease.com',
                'wallet_balance': 0.0,
                'created_at': firestore.SERVER_TIMESTAMP
             })
             raise ValueError("User initialized. Please add funds and try again.")
        
        userData = snapshot.to_dict()
        
        # 1. Check Balance
        current_balance = userData.get('wallet_balance', 0)
        if current_balance < daily_charge:
            raise ValueError("Insufficient balance")
            
        # 2. Check Daily Limit
        last_check_in = userData.get('last_check_in')
        if last_check_in:
            # Convert timestamp to date
            last_date = last_check_in.date()
            today = datetime.now().date()
            if last_date == today:
                 raise ValueError("Already checked in today")
        
        # 3. Deduct & Update
        new_balance = current_balance - daily_charge
        transaction.update(ref, {
            'wallet_balance': new_balance,
            'last_check_in': datetime.now(),
            'current_vehicle': vehicle_number
        })
        return new_balance

    try:
        transaction = db.transaction()
        new_bal = check_in_transaction(transaction, user_ref)
        
        # Log transaction
        db.collection('transactions').add({
            'uid': uid,
            'amount': daily_charge,
            'type': 'DEBIT_PARKING',
            'vehicle': vehicle_number,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        return {"success": True, "new_balance": new_bal, "message": "Check-in successful"}
    except ValueError as ve:
        return {"success": False, "message": str(ve)}
    except Exception as e:
        print(f"Check-in error: {e}")
        return {"success": False, "message": f"System error: {str(e)}"}
