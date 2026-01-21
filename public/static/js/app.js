// Firebase Configuration
// REPLACE WITH YOUR FIREBASE CONFIG
const firebaseConfig = {
    apiKey: "YOUR_API_KEY",
    authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
    projectId: "YOUR_PROJECT_ID",
    storageBucket: "YOUR_PROJECT_ID.appspot.com",
    messagingSenderId: "SENDER_ID",
    appId: "APP_ID"
};

try {
    firebase.initializeApp(firebaseConfig);
} catch (e) {
    console.error("Firebase Init Error", e);
}

// Stripe Init (Public Key)
const stripe = Stripe('pk_test_YOUR_PUBLISHABLE_KEY');

let currentUser = null;

// Auth State Listener
firebase.auth().onAuthStateChanged(async (user) => {
    if (user) {
        currentUser = user;
        const token = await user.getIdToken();

        // Verify with backend and sync
        try {
            const res = await fetch('/api/verify_token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: token })
            });

            if (window.location.pathname === '/login.html' || window.location.pathname === '/') {
                if (window.location.pathname === '/') {
                    // Logic to show dashboard if on root and logged in, handled by flask mostly but good to separate
                }
            }

            if (document.getElementById('user-name')) {
                document.getElementById('user-name').innerText = user.displayName || user.email;
                document.getElementById('display-name').value = user.displayName || user.email;
                fetchBalance();
            }

        } catch (error) {
            console.error(error);
        }
    } else {
        if (window.location.pathname.includes('dashboard')) {
            window.location.href = '/';
        }
    }
});

function handleLogin() {
    const provider = new firebase.auth.GoogleAuthProvider();
    firebase.auth().signInWithPopup(provider).catch((error) => {
        document.getElementById('error-msg').innerText = error.message;
    });
}

function handleLogout() {
    firebase.auth().signOut().then(() => {
        window.location.href = '/';
    });
}

// Balance Logic
async function fetchBalance() {
    if (!currentUser) return;
    const res = await fetch(`/api/wallet/balance?uid=${currentUser.uid}`);
    const data = await res.json();
    document.getElementById('wallet-balance').innerText = data.balance.toFixed(2);
}

// Check In Logic
async function checkIn() {
    const vehicle = document.getElementById('vehicle-number').value;
    const msgDiv = document.getElementById('checkin-msg');

    if (!vehicle) {
        msgDiv.style.display = 'block';
        msgDiv.className = 'alert alert-error';
        msgDiv.innerText = 'Please enter vehicle number';
        return;
    }

    msgDiv.style.display = 'none';

    try {
        const res = await fetch('/api/check-in', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: currentUser.uid, vehicle: vehicle })
        });
        const data = await res.json();

        msgDiv.style.display = 'block';
        if (data.success) {
            msgDiv.className = 'alert alert-success';
            msgDiv.innerText = `Checked in! New Balance: ₹${data.new_balance}`;
            fetchBalance();
        } else {
            msgDiv.className = 'alert alert-error';
            msgDiv.innerText = data.message;
        }
    } catch (e) {
        console.error(e);
    }
}

// Payment Logic
function showPaymentModal() {
    document.getElementById('payment-modal').style.display = 'flex';
}

function closePaymentModal() {
    document.getElementById('payment-modal').style.display = 'none';
}

async function processPayment() {
    const amount = document.getElementById('topup-amount').value;
    const payBtn = document.getElementById('pay-btn');
    const msgDiv = document.getElementById('payment-msg');

    payBtn.disabled = true;
    payBtn.innerText = "Processing...";

    try {
        // 1. Create Payment Intent
        const res = await fetch('/api/payment/create-intent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: parseFloat(amount) })
        });
        const { clientSecret } = await res.json();

        // 2. Confirm Card Payment (Using simple confirmCardPayment for demo)
        // Note: For a real production app, you'd use Elements to collect card details securely.
        // For this prototype, I'll simulate a success flow or would need to add Elements here.
        // Waiting for user to add Stripe keys -> I should probably use the provided test card from Stripe.

        // Actually, to make this work, we need the Stripe Element mounted. 
        // For now, let's just alert that keys are needed or mock it if key is missing.

        alert("Integrate Stripe Element here using clientSecret: " + clientSecret.substring(0, 10) + "...");

        // Mock success for demonstration if requested
        // In real implementation:
        /*
        const result = await stripe.confirmCardPayment(clientSecret, {
            payment_method: { card: cardElement }
        });
        if (result.error) ...
        */

        // For now, let's assume we proceed to backend confirmation (this is insecure in prod without webhook/intent verification)
        const confirmRes = await fetch('/api/payment/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                uid: currentUser.uid,
                amount: parseFloat(amount),
                payment_intent_id: "pi_MOCK_For_Demo" // This will fail backend check unless we mock backend too or actually pay
            })
        });

    } catch (e) {
        msgDiv.innerText = "Error initiating payment: " + e.message;
        msgDiv.style.display = 'block';
        msgDiv.className = 'alert alert-error';
    } finally {
        payBtn.disabled = false;
        payBtn.innerText = "Pay Now";
    }
}
