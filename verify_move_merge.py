import db
import uuid
import datetime

def run_verification():
    print("--- VERIFICATION: ASSET MOVE/MERGE ---")
    
    # 1. Setup User & Wallets
    username = f"move_user_{uuid.uuid4().hex[:8]}"
    print(f"Creating user: {username}")
    db.create_user(username, "pass123", f"{username}@example.com")
    user = db.verify_user(username, "pass123")
    user_id = user['id']
    
    db.create_wallet(user_id, "Wallet A")
    db.create_wallet(user_id, "Wallet B")
    wallets = db.get_wallets(user_id)
    w_a = wallets[wallets['name'] == "Wallet A"].iloc[0]['id']
    w_b = wallets[wallets['name'] == "Wallet B"].iloc[0]['id']
    
    print(f"Wallet A ID: {w_a}, Wallet B ID: {w_b}")

    # 2. Test MOVE (No Collision)
    print("Test 1: Simple Move")
    db.add_to_wallet(user_id, "PETR4", 100, 30.0, w_a)
    
    print("Moving PETR4 from A to B...")
    # Change Wallet A -> B
    success, msg = db.update_wallet_item(user_id, "PETR4", 100, 30.0, wallet_id=w_a, new_wallet_id=w_b)
    print(f"Result: {msg}")
    
    # Verify
    p_a = db.get_portfolio(user_id, wallet_id=w_a)
    p_b = db.get_portfolio(user_id, wallet_id=w_b)
    
    if "PETR4" not in p_a['ticker'].values and "PETR4" in p_b['ticker'].values:
        print("PASS: Simple Move")
    else:
        print("FAIL: Simple Move")

    # 3. Test MERGE (Collision)
    print("Test 2: Merge Collision")
    # Setup: VALE3 in A (50 @ 10) and VALE3 in B (50 @ 20)
    db.add_to_wallet(user_id, "VALE3", 50, 10.0, w_a)
    db.add_to_wallet(user_id, "VALE3", 50, 20.0, w_b)
    
    print("Moving VALE3 from A to B (Merge)...")
    # Should result in B having 100 @ 15.0
    success, msg = db.update_wallet_item(user_id, "VALE3", 50, 10.0, wallet_id=w_a, new_wallet_id=w_b)
    print(f"Result: {msg}")
    
    p_a = db.get_portfolio(user_id, wallet_id=w_a)
    p_b = db.get_portfolio(user_id, wallet_id=w_b)
    
    if not p_a.empty and "VALE3" in p_a['ticker'].values:
         print("FAIL: Source not deleted.")
    else:
         row_b = p_b[p_b['ticker'] == "VALE3"].iloc[0]
         qty = row_b['quantity']
         avg = row_b['avg_price']
         print(f"Target State: Qty={qty}, Avg={avg}")
         
         if int(qty) == 100 and abs(avg - 15.0) < 0.1:
             print("PASS: Merge Logic")
         else:
             print("FAIL: Merge Logic")

    print("--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    run_verification()
