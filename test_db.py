import db
import os

print("--- Testing DB Init ---")
# Reset DB for test
if os.path.exists("market_hacking.db"):
    os.remove("market_hacking.db")

db.init_db()
print("DB Initialized.")

print("--- Testing User Creation ---")
ok, msg = db.create_user("testuser", "password123", "test@example.com")
print(f"Create User: {ok} - {msg}")

print("--- Testing User Verification ---")
user = db.verify_user("testuser", "password123")
print(f"Verify User: {user}")

if user:
    uid = user['id']
    print("--- Testing Wallet Add ---")
    ok, msg = db.add_to_wallet(uid, "VALE3", 100, 50.0)
    print(f"Add Wallet: {ok} - {msg}")
    
    print("--- Testing Get Portfolio ---")
    df = db.get_portfolio(uid)
    print(df)
    
print("--- TEST COMPLETE ---")
