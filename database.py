"""SQLite database schema, installation, demo seed, and password helpers.

No data is held in localStorage or a fake JSON database. The SQLite file persists
products, actual sale lines, stock movements, administrators and sessions.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

PBKDF2_ITERATIONS = 310_000


def password_hash(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, expected: str, salt: str) -> bool:
    digest, _ = password_hash(password, salt)
    return secrets.compare_digest(digest, expected)


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    cost_cents INTEGER NOT NULL CHECK(cost_cents >= 0),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    min_stock INTEGER NOT NULL DEFAULT 10 CHECK(min_stock >= 0),
    unit TEXT NOT NULL DEFAULT 'pcs',
    archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    change_amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    actor_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_movements_date ON stock_movements(created_at DESC);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no TEXT NOT NULL UNIQUE,
    total_cents INTEGER NOT NULL CHECK(total_cents > 0),
    payment_method TEXT NOT NULL,
    actor_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(created_at DESC);
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL,
    unit_cost_cents INTEGER NOT NULL,
    line_total_cents INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
"""

DEMO_PRODUCTS = [
    ("BRD-001", "Classic Pandesal", "Everyday Bread", 500, 260, 250, 35, "pcs"),
    ("BRD-002", "Ube Cheese Pandesal", "Everyday Bread", 1800, 960, 105, 25, "pcs"),
    ("BRD-003", "Spanish Bread", "Everyday Bread", 1500, 750, 100, 20, "pcs"),
    ("BRD-004", "Cheese Roll", "Pastries", 3200, 1700, 65, 15, "pcs"),
    ("BRD-005", "Ensaymada", "Pastries", 3800, 2000, 48, 12, "pcs"),
    ("BRD-006", "Butter Croissant", "Pastries", 6500, 3500, 34, 12, "pcs"),
    ("BRD-007", "Chocolate Croissant", "Pastries", 7800, 4200, 29, 10, "pcs"),
    ("BRD-008", "Cinnamon Roll", "Sweet Treats", 5500, 3000, 42, 12, "pcs"),
    ("BRD-009", "Banana Bread Slice", "Sweet Treats", 4500, 2100, 46, 12, "pcs"),
    ("BRD-010", "Milk Bread Loaf", "Loaves", 11000, 6200, 32, 10, "loaf"),
    ("BRD-011", "Sourdough Loaf", "Loaves", 18000, 10000, 26, 10, "loaf"),
    ("BRD-012", "Garlic Baguette", "Specialty Bread", 9000, 4800, 30, 10, "pcs"),
    ("BRD-013", "Strawberry Danish", "Pastries", 8500, 4700, 24, 10, "pcs"),
]


def seed_demo(conn: sqlite3.Connection) -> None:
    # Seed only if the products table is empty. All sales are real linked records,
    # and stock is deducted inside the same transaction as the sale.
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
        return
    for p in DEMO_PRODUCTS:
        conn.execute("""INSERT INTO products
            (sku,name,category,price_cents,cost_cents,quantity,min_stock,unit)
            VALUES (?,?,?,?,?,?,?,?)""", p)
    base = (datetime.now() - timedelta(hours=5)).replace(minute=0, second=0, microsecond=0)
    for day in range(13, -1, -1):
        for index in range(1 + ((day * 7) % 3)):
            stamp = (base - timedelta(days=day) + timedelta(hours=index*2)).strftime("%Y-%m-%d %H:%M:%S")
            choices = [1 + (day + index*3) % 11, 1 + (day*3+index*5) % 13]
            if day % 3 == 0:
                choices.append(2)
            lines = []
            for idx, product_id in enumerate(choices):
                row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                amount = 1 + ((day + index + idx) % 3)
                if row["quantity"] < amount:
                    continue
                lines.append((row, amount))
            if not lines:
                continue
            total = sum(row["price_cents"]*q for row, q in lines)
            receipt = f"DEMO-{day:02d}-{index:02d}"
            sale_id = conn.execute("""INSERT INTO sales
                (receipt_no,total_cents,payment_method,created_at)
                VALUES (?,?,?,?)""", (receipt,total,"Cash" if index % 2 == 0 else "GCash",stamp)).lastrowid
            for row,q in lines:
                conn.execute("""INSERT INTO sale_items
                    (sale_id,product_id,product_name,quantity,unit_price_cents,unit_cost_cents,line_total_cents)
                    VALUES (?,?,?,?,?,?,?)""",
                    (sale_id,row["id"],row["name"],q,row["price_cents"],row["cost_cents"],q*row["price_cents"]))
                conn.execute("UPDATE products SET quantity=quantity-? WHERE id=?", (q,row["id"]))
                conn.execute("""INSERT INTO stock_movements
                    (product_id,change_amount,reason,note,created_at) VALUES (?,?,?,?,?)""",
                    (row["id"],-q,"Sale",receipt,stamp))
    # A few realistic low-stock items to make demo alerts meaningful.
    for prod_id, quantity in [(5,8),(7,6),(12,3),(13,0)]:
        before = conn.execute("SELECT quantity FROM products WHERE id=?", (prod_id,)).fetchone()[0]
        conn.execute("UPDATE products SET quantity=? WHERE id=?", (quantity,prod_id))
        conn.execute("""INSERT INTO stock_movements
            (product_id,change_amount,reason,note) VALUES (?,?,?,?)""",
            (prod_id,quantity-before,"Demo setup","Sample inventory count"))


def initialize(path: str | Path, demo: bool = True) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with connect(p) as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            email = os.getenv("ADMIN_EMAIL", "admin@breadstore.local").lower().strip()
            password = os.getenv("ADMIN_PASSWORD")
            if not password:
                password = secrets.token_urlsafe(16)
                print("\n" + "=" * 64, flush=True)
                print(f"BreadStore login email: {email}", flush=True)
                print(f"BreadStore one-time admin password: {password}", flush=True)
                print("Save this now; it will not be shown again. Set ADMIN_PASSWORD", flush=True)
                print("in .env BEFORE FIRST RUN to choose your own password.", flush=True)
                print("=" * 64 + "\n", flush=True)
            password_digest, salt = password_hash(password)
            conn.execute("INSERT INTO users(email,password_hash,salt) VALUES (?,?,?)", (email,password_digest,salt))
        if demo:
            seed_demo(conn)
