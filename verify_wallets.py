import db
import uuid
import datetime

def run_verification():
    print("--- VERIFICATION: WALLET BACKEND ---")
    
    # 1. Create Temporary User
    username = f"test_user_{uuid.uuid4().hex[:8]}"
    print(f"Creating user: {username}")
    success, msg = db.create_user(username, "pass123", f"{username}@example.com")
    if not success:
        print(f"FAIL: {msg}")
        return

    # Get User ID
    user_data = db.verify_user(username, "pass123")
    user_id = user_data['id']
    print(f"User ID: {user_id}")

    # 2. Check Default Wallet
    wallets = db.get_wallets(user_id)
    print(f"Wallets after creation: {[w['name'] for _, w in wallets.iterrows()]}")
    if "Carteira Principal" not in wallets['name'].values:
        print("FAIL: Default wallet not created.")
    else:
        print("PASS: Default wallet created.")

    # 3. Create New Wallet
    print("Creating 'Investimentos USA'...")
    db.create_wallet(user_id, "Investimentos USA")
    wallets = db.get_wallets(user_id)
    print(f"Wallets: {[w['name'] for _, w in wallets.iterrows()]}")
    
    w_principal = wallets[wallets['name'] == "Carteira Principal"].iloc[0]['id']
    w_usa = wallets[wallets['name'] == "Investimentos USA"].iloc[0]['id']

    # 4. Add Assets
    print("Adding AAPL to USA...")
    db.add_to_wallet(user_id, "AAPL", 10, 150.0, w_usa)
    
    print("Adding VALE3 to Principal...")
    db.add_to_wallet(user_id, "VALE3", 100, 60.0, w_principal)
    
    # 5. Verify Isolation
    print("Checking USA Wallet...")
    port_usa = db.get_portfolio(user_id, wallet_id=w_usa)
    tickers_usa = port_usa['ticker'].tolist()
    print(f"USA Tickers: {tickers_usa}")
    if "AAPL" in tickers_usa and "VALE3" not in tickers_usa:
        print("PASS: USA Wallet isolation.")
    else:
        print("FAIL: USA Wallet isolation.")

    print("Checking Principal Wallet...")
    port_prin = db.get_portfolio(user_id, wallet_id=w_principal)
    tickers_prin = port_prin['ticker'].tolist()

    print(f"Principal Tickers: {tickers_prin}")
    if "VALE3" in tickers_prin and "AAPL" not in tickers_prin:
        print("PASS: Principal Wallet isolation.")
    else:
        print("FAIL: Principal Wallet isolation.")

    # 6. Verify Aggregation
    print("Checking ALL Wallets...")
    port_all = db.get_portfolio(user_id) # No wallet_id
    tickers_all = port_all['ticker'].tolist()
    print(f"All Tickers: {tickers_all}")
    if "AAPL" in tickers_all and "VALE3" in tickers_all:
         print("PASS: Aggregation.")
    else:
         print("FAIL: Aggregation.")

    # 7. Update Asset (USA)
    print("Updating AAPL in USA...")
    db.update_wallet_item(user_id, "AAPL", 20, 155.0, wallet_id=w_usa)
    port_usa_upd = db.get_portfolio(user_id, wallet_id=w_usa)
    qty = port_usa_upd[port_usa_upd['ticker'] == 'AAPL'].iloc[0]['quantity']
    if int(qty) == 20:
        print("PASS: Update.")
    else:
        print(f"FAIL: Update. Got {qty}")

    # 8. Remove Asset
    print("Removing VALE3 from Principal...")
    db.remove_from_wallet(user_id, "VALE3", wallet_id=w_principal)
    port_prin_del = db.get_portfolio(user_id, wallet_id=w_principal)
    if port_prin_del.empty:
        print("PASS: Removal.")
    else:
        print("FAIL: Removal.")

    print("--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    run_verification()
