BREADSTORE COMPLETE — ADMIN + CUSTOMER (WINDOWS)
================================================
ONE folder includes both websites and one shared real SQLite database.

QUICK START (no copying code files):
1. Extract BreadStore-Complete-Admin-Customer.zip using "Extract All".
2. Open the ONE folder named BreadStore-Complete-Admin-Customer.
3. Double-click START_BREADSTORE.bat and wait for "Application startup complete".
   It will install required Python packages if necessary. Internet is needed
   for the first package installation. Python must be installed on Windows.
4. Open either site in your browser:
   ADMIN:      http://127.0.0.1:8000/
   CUSTOMER:   http://127.0.0.1:8000/shop
   Or double-click OPEN_ADMIN.bat / OPEN_CUSTOMER.bat.

KEEPING YOUR OLD BREADSTORE DATA:
- Stop the old VS Code server FIRST (Ctrl+C) so the port is free.
- On first startup, START_BREADSTORE.bat checks for your old database at
  D:\BreadStore-Inventory-System\BreadStore-Inventory\datareadstore.db
  or in a neighboring BreadStore-Inventory folder and copies it to
  this folder's datareadstore.db (only if that file does not exist).
- Old products, old sales and your old admin password will remain available.
- This is a COPY, so the previous database is left unchanged.
- No existing database will be overwritten by the launcher.
- If you put the folder elsewhere, these paths are still checked.
- To switch to an EMPTY new database, stop the server, rename the current
  datareadstore.db to a backup outside this folder, and move/rename the
  OLD project folder to prevent the launcher from copying it again.
  [Note: a fresh database starts with demo products unless SEED_DEMO=false.]

FIRST-TIME ADMIN LOGIN WITH NO OLD DATABASE:
- The terminal prints an auto-generated one-time admin password once.
- Email: admin@breadstore.local
- Save that password safely.
- To pick your own password BEFORE THE FIRST RUN, create a .env file from
  .env.example and edit ADMIN_PASSWORD. Password must be 12+ characters.
- Changing ADMIN_PASSWORD later does NOT reset an existing admin account.

CUSTOMER FUNCTIONS:
- Open /shop; register a new customer; add products to cart; place pickup orders.
- Admin can view orders and advance Pending > Preparing > Ready > Completed.
- Cancelled orders restore stock; completed pickups appear in sales reports.
- Checkout is PAY AT PICKUP only, NOT online payment.

IF SOMETHING GOES WRONG:
- Make sure no other BreadStore instance is running on port 8000.
- Keep the black launcher window open while using the website.
- If Python is not found, install Python 3.11+ for Windows.
- See README.md, docs\CUSTOMER_ORDERING.md, and docs\DEFENSE_GUIDE.md.

PLEASE DO NOT UPLOAD YOUR DATABASE OR .env TO PUBLIC GITHUB.
