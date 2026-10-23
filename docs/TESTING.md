# Testing and test evidence

## Automated backend test result

At project creation, six integration tests were run with `python -m pytest -q` using isolated temporary SQLite databases:

```text
......                                                                   [100%]
6 passed
```

The tests confirm:

| Case | Action | Expected result | Observed in automated run |
|---|---|---|---|
| TC-01 | Unauthenticated inventory request | HTTP 401 | Pass |
| TC-02 | Cross-origin-style mutation without required header | HTTP 403 | Pass |
| TC-03 | Valid login + logout | Authorized session, then HTTP 401 | Pass |
| TC-04 | Create product with valid values | Row inserted | Pass |
| TC-05 | Duplicate SKU | HTTP 409, no duplicate | Pass |
| TC-06 | Search by product name | Matching rows returned | Pass |
| TC-07 | Update product, archive and restore | Existing row updates, history retained | Pass |
| TC-08 | Negative price or malformed SKU | HTTP 422 | Pass |
| TC-09 | Restock then try excessive negative adjustment | Correct stock, rejected invalid deduction | Pass |
| TC-10 | Buy more stock than available | HTTP 409, entire sale rolled back | Pass |
| TC-11 | Successful two-product checkout | Sale saved, correct total, stock reduced | Pass |
| TC-12 | Sales and profit report calculations | Correct totals from sale lines | Pass |
| TC-13 | CSV export | Valid response containing product data | Pass |
| TC-14 | Change password | New password works; previous password rejected | Pass |

### How to reproduce

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests **do not** modify the default production database because they each create a temporary database. Testing a production store, host configuration or parallel multi-user performance requires extra work.

## Browser smoke walkthrough

A headless Chromium walkthrough used the real frontend HTML/CSS/JavaScript and connected its fetch requests to the real FastAPI TestClient using a bridge (because direct browser network navigation was blocked in the build environment). The following actions ran without browser JavaScript exceptions:

1. Render sign-in page and sign in with a generated test administrator.
2. Load overview cards, graph and low-stock records.
3. Open Add Product modal and save one bread product.
4. Navigate to Inventory, search for the new product, and confirm the match.
5. Open Point of Sale, search for the product, add one to cart, complete sale.
6. Confirm the new sale shows in sales history, open reports.

Screenshots: `docs/screenshots/login.png`, `dashboard.png`, `inventory.png`, `point-of-sale.png`, `reports.png`.

## Manual acceptance testing — student to complete locally

Fill the Result column **after running the project yourself**; it is intentionally blank.

| Procedure | Expected result | Your result/date |
|---|---|---|
| Login with correct admin credentials | Dashboard loads | _To verify_ |
| Login with incorrect password | Clear error, still signed out | _To verify_ |
| Add bread with SKU, cost, price, minimum stock | Product appears in inventory | _To verify_ |
| Try duplicate SKU | Rejected with readable message | _To verify_ |
| Search products by name and SKU | Matches found | _To verify_ |
| Add 20 units via Stock Adjustment | Quantity increases by 20, event logged | _To verify_ |
| Sell 2 pieces | Quantity drops by 2, receipt saved | _To verify_ |
| Sell more than available | No sale made, stock unchanged | _To verify_ |
| Archive product | Hidden from active products, still in past sales | _To verify_ |
| Open Reports and select last 7/30/90 days | Charts change; recorded totals consistent | _To verify_ |
| Export CSV and open in Excel | Product/sale data appears in columns | _To verify_ |
| Restart server | Existing data still available | _To verify_ |
| Resize browser to mobile width | Sidebar menu and content remain usable | _To verify_ |

## Troubleshooting notes

- **Python command not found:** install Python, ensure it is added to PATH or use `py` on Windows.
- **`uvicorn` not installed:** activate the virtual environment and run `pip install -r requirements.txt`.
- **Login credentials don't work:** existing passwords are stored in the DB. Changing `.env` later does not overwrite them. Use Settings or `python admin_tools.py`.
- **Port 8000 busy:** start with `python -m uvicorn app:app --reload --port 8001` and open port 8001 instead.
- **Database locked:** do not run multiple development servers against the same SQLite file; avoid long-running writes. DB uses busy timeout and atomic transactions.
- **Chart is empty:** when demo seeding is turned off, enter products and make sales first.
- **Environment variables ignored on running server:** stop and restart the server to read `.env` again.

## Known limitations of this test evidence

Test outputs verify the provided source in the build environment, **not** every user's Windows machine, hosting environment or browser. Students should personally verify and record their own results before submission.


## Version 2 customer-order tests (October 20, 2026)

Five additional integration tests were added in `tests/test_customers.py`, increasing total to **11 passing tests** using temporary SQLite databases. They cover:

1. Customer registration, login, logout, validation and customer/admin authorization separation.
2. Public storefront catalog (cost prices not exposed), out-of-stock rejection, atomic stock reservation and reversible cancellation.
3. Admin progression `Pending → Preparing → Ready → Completed`, exactly one saved sale per completed pickup, and no second stock deduction.
4. Separation of customer order histories, unauthorized status changes, and rejecting oversized item quantities.
5. Backward-compatible schema creation on a pre-existing database without deleting original products.

In an isolated browser UI check with the application API bridged to FastAPI TestClient, the customer catalog rendered 13 demonstration products, a customer registered, submitted an order, saw their order history, and the administrator's order view displayed the same order. Because direct local URL navigation was blocked in this build environment, confirm normal browser navigation and all status-changing buttons on your own machine.

Manual demonstration to complete locally: open `/shop` on your Windows PC, register a test account, order 2 bread items, open `/#orders` as admin, mark Preparing → Ready → Completed and check Reports. Create a second order and cancel it to verify stock restoration. Record screenshots and any errors in your own testing log.
