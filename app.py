"""BreadStore: FastAPI + a real, file-backed SQLite inventory and POS system.

Start with: python -m uvicorn app:app --reload
The API uses prepared SQL parameters, HttpOnly database-backed session cookies,
strong password hashes, validation, stock-aware transactions and activity logs.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import logging
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from database import connect, initialize, password_hash, verify_password

BASE_DIR = Path(__file__).resolve().parent

# Small .env loader: no extra package is needed, and real environment variables
# override the local file. Only simple KEY=VALUE lines are supported.
def load_local_env():
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

load_local_env()
logger = logging.getLogger("breadstore")
SESSION_SECONDS = 12 * 60 * 60
MAX_STOCK = 1_000_000


def local_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def utc_time(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")


def clean_str(value: str) -> str:
    return " ".join(value.strip().split())


def cents(amount: Decimal) -> int:
    return int(amount * 100)


def product_json(row: sqlite3.Row) -> dict:
    p = dict(row)
    p["price"] = round(p.pop("price_cents") / 100, 2)
    p["cost"] = round(p.pop("cost_cents") / 100, 2)
    p["status"] = ("Archived" if p["archived"] else "Out of stock" if p["quantity"] == 0
                   else "Low stock" if p["quantity"] <= p["min_stock"] else "In stock")
    return p


class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


class ProductIn(BaseModel):
    sku: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=80)
    category: str = Field(min_length=2, max_length=60)
    price: Decimal = Field(gt=0, le=1000000, decimal_places=2)
    cost: Decimal = Field(ge=0, le=1000000, decimal_places=2)
    min_stock: int = Field(ge=0, le=MAX_STOCK)
    unit: Literal["pcs", "loaf", "pack", "box"] = "pcs"

    @field_validator("sku")
    @classmethod
    def valid_sku(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,29}", value):
            raise ValueError("SKU must have 2–30 letters, numbers, hyphens or underscores.")
        return value

    @field_validator("name", "category")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = clean_str(value)
        if len(value) < 2:
            raise ValueError("This field must contain at least 2 characters.")
        return value


class NewProductIn(ProductIn):
    quantity: int = Field(ge=0, le=MAX_STOCK)


class AdjustIn(BaseModel):
    change: int = Field(ge=-MAX_STOCK, le=MAX_STOCK)
    reason: Literal["Restock", "Damage / waste", "Inventory correction"]
    note: str = Field(default="", max_length=200)

    @field_validator("change")
    @classmethod
    def nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Stock adjustment cannot be zero.")
        return value


class SaleLine(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=10000)


class SaleIn(BaseModel):
    items: list[SaleLine] = Field(min_length=1, max_length=40)
    payment_method: Literal["Cash", "GCash", "Card"]


def create_app(database_path: str | Path | None = None, demo: bool | None = None) -> FastAPI:
    path = Path(database_path or os.getenv("DB_PATH") or BASE_DIR / "data" / "breadstore.db").resolve()
    if demo is None:
        demo = os.getenv("SEED_DEMO", "true").lower() not in ("false", "0", "no")
    initialize(path, demo=demo)
    api = FastAPI(title="BreadStore Inventory API", version="1.0.0", docs_url="/api/docs", redoc_url=None)
    api.state.db_path = path
    api.state.login_attempts = {}
    api.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    def db():
        cn = connect(path)
        try:
            yield cn
        finally:
            cn.close()

    def user(request: Request, cn: sqlite3.Connection = Depends(db)) -> dict:
        token = request.cookies.get("breadstore_session", "")
        if len(token) < 20:
            raise HTTPException(status_code=401, detail="Please sign in to continue.")
        hash_token = hashlib.sha256(token.encode()).hexdigest()
        row = cn.execute("""SELECT u.id,u.email,s.id AS session_id FROM sessions s
            JOIN users u ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?""",
            (hash_token, utc_time())).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
        return dict(row)

    @api.middleware("http")
    async def request_checks(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            # JSON requests from other origins cannot supply this non-simple header
            # without a CORS preflight; this API intentionally enables no CORS.
            if request.headers.get("X-Requested-With") != "BreadStore":
                return JSONResponse({"detail": "Invalid request header."}, status_code=403)
            origin = request.headers.get("origin")
            if origin:
                from urllib.parse import urlparse
                if urlparse(origin).netloc.lower() != request.headers.get("host", "").lower():
                    return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @api.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        errs = exc.errors()
        detail = errs[0].get("msg", "Invalid form data.") if errs else "Invalid form data."
        if detail.startswith("Value error, "):
            detail = detail[13:]
        return JSONResponse({"detail": detail, "errors": [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in errs]}, status_code=422)

    @api.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        logger.exception("Unexpected server error: %s", exc)
        return JSONResponse({"detail": "An unexpected error occurred. Please try again."}, status_code=500)

    @api.get("/api/health")
    def health():
        with connect(path) as cn:
            cn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "connected"}

    @api.get("/")
    def index():
        return FileResponse(BASE_DIR / "static" / "index.html")

    @api.get("/api/auth/me")
    def me(current=Depends(user)):
        return {"id":current["id"], "email":current["email"], "role":"Administrator"}

    @api.post("/api/auth/login")
    def login(form: LoginIn, request: Request, cn: sqlite3.Connection = Depends(db)):
        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        # A simple per-IP attempt limiter. For public multi-server deployments,
        # use a shared reverse-proxy or Redis rate limiter instead.
        attempts = [x for x in api.state.login_attempts.get(key, []) if now-x < 600]
        if len(attempts) >= 10:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 10 minutes.")
        row = cn.execute("SELECT * FROM users WHERE email=?", (form.email.strip(),)).fetchone()
        # Hash work even for unknown accounts to reduce user enumeration timing.
        if row:
            valid = verify_password(form.password,row["password_hash"],row["salt"])
        else:
            password_hash(form.password, "0"*32)
            valid = False
        if not valid:
            attempts.append(now)
            api.state.login_attempts[key] = attempts
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        api.state.login_attempts.pop(key, None)
        raw = secrets.token_urlsafe(32)
        expiry = utc_time(datetime.now(timezone.utc)+timedelta(seconds=SESSION_SECONDS))
        with cn:
            cn.execute("DELETE FROM sessions WHERE expires_at<=?", (utc_time(),))
            cn.execute("INSERT INTO sessions(user_id,token_hash,expires_at) VALUES (?,?,?)",
                       (row["id"],hashlib.sha256(raw.encode()).hexdigest(),expiry))
        resp = JSONResponse({"id":row["id"], "email":row["email"], "role":"Administrator"})
        is_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true" or request.url.scheme == "https"
        resp.set_cookie("breadstore_session", raw, max_age=SESSION_SECONDS, path="/", httponly=True, samesite="strict", secure=is_secure)
        return resp

    @api.post("/api/auth/logout")
    def logout(request: Request, current=Depends(user), cn: sqlite3.Connection = Depends(db)):
        token = request.cookies.get("breadstore_session", "")
        with cn:
            cn.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        resp = JSONResponse({"message":"Signed out successfully."})
        resp.delete_cookie("breadstore_session",path="/")
        return resp

    @api.post("/api/auth/change-password")
    def change_password(form: PasswordIn, current=Depends(user), cn: sqlite3.Connection = Depends(db)):
        row = cn.execute("SELECT * FROM users WHERE id=?",(current["id"],)).fetchone()
        if not verify_password(form.current_password,row["password_hash"],row["salt"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if form.new_password == form.current_password:
            raise HTTPException(status_code=400, detail="Choose a different new password.")
        digest,salt=password_hash(form.new_password)
        with cn:
            cn.execute("UPDATE users SET password_hash=?,salt=? WHERE id=?",(digest,salt,current["id"]))
            cn.execute("DELETE FROM sessions WHERE user_id=? AND id<>?",(current["id"],current["session_id"]))
        return {"message":"Password updated. Other sessions have been signed out."}

    @api.get("/api/products")
    def get_products(q: str="", category: str="All", status: str="All", sort: str="name", _=Depends(user), cn: sqlite3.Connection=Depends(db)):
        clauses = ["1=1"]
        args = []
        if status == "Archived":
            clauses.append("archived=1")
        else:
            clauses.append("archived=0")
        if q.strip():
            clauses.append("(name LIKE ? OR sku LIKE ? OR category LIKE ?)")
            like = f"%{q.strip()[:100]}%"
            args.extend([like,like,like])
        if category != "All":
            clauses.append("category=?")
            args.append(category)
        if status == "Low stock":
            clauses.append("quantity>0 AND quantity<=min_stock")
        elif status == "Out of stock":
            clauses.append("quantity=0")
        elif status == "In stock":
            clauses.append("quantity>min_stock")
        orders = {"name":"name COLLATE NOCASE", "stock":"quantity ASC, name", "price":"price_cents DESC", "newest":"id DESC"}
        sql = "SELECT * FROM products WHERE " + " AND ".join(clauses) + " ORDER BY " + orders.get(sort,"name COLLATE NOCASE")
        rows=cn.execute(sql,args).fetchall()
        categories=[r[0] for r in cn.execute("SELECT DISTINCT category FROM products WHERE archived=0 ORDER BY category").fetchall()]
        return {"products":[product_json(r) for r in rows],"categories":categories}

    @api.post("/api/products",status_code=201)
    def create_product(form: NewProductIn, current=Depends(user), cn: sqlite3.Connection=Depends(db)):
        try:
            with cn:
                cur=cn.execute("""INSERT INTO products
                    (sku,name,category,price_cents,cost_cents,quantity,min_stock,unit)
                    VALUES (?,?,?,?,?,?,?,?)""", (form.sku,form.name,form.category,cents(form.price),cents(form.cost),form.quantity,form.min_stock,form.unit))
                if form.quantity:
                    cn.execute("""INSERT INTO stock_movements
                        (product_id,change_amount,reason,note,actor_id) VALUES (?,?,?,?,?)""",
                        (cur.lastrowid,form.quantity,"Initial stock","Product created",current["id"]))
                row=cn.execute("SELECT * FROM products WHERE id=?",(cur.lastrowid,)).fetchone()
            return product_json(row)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409,detail="This SKU already exists. Please use a unique SKU.")

    @api.put("/api/products/{product_id}")
    def update_product(product_id:int,form:ProductIn,_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        if not cn.execute("SELECT 1 FROM products WHERE id=? AND archived=0",(product_id,)).fetchone():
            raise HTTPException(status_code=404,detail="Product not found.")
        try:
            with cn:
                cn.execute("""UPDATE products SET sku=?,name=?,category=?,price_cents=?,cost_cents=?,min_stock=?,unit=?,updated_at=?
                    WHERE id=?""", (form.sku,form.name,form.category,cents(form.price),cents(form.cost),form.min_stock,form.unit,local_time(),product_id))
            return product_json(cn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone())
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409,detail="This SKU already exists. Please use a unique SKU.")

    @api.delete("/api/products/{product_id}")
    def archive_product(product_id:int,_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        with cn:
            result=cn.execute("UPDATE products SET archived=1,updated_at=? WHERE id=? AND archived=0", (local_time(),product_id))
        if result.rowcount==0:
            raise HTTPException(status_code=404,detail="Product not found or already archived.")
        return {"message":"Product archived. Previous sales and stock history are preserved."}

    @api.post("/api/products/{product_id}/restore")
    def restore_product(product_id:int,_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        with cn:
            result=cn.execute("UPDATE products SET archived=0,updated_at=? WHERE id=? AND archived=1", (local_time(),product_id))
        if result.rowcount==0:
            raise HTTPException(status_code=404,detail="Archived product not found.")
        return {"message":"Product restored."}

    @api.post("/api/products/{product_id}/adjust")
    def adjust_stock(product_id:int,form:AdjustIn,current=Depends(user),cn:sqlite3.Connection=Depends(db)):
        try:
            cn.execute("BEGIN IMMEDIATE")
            row=cn.execute("SELECT * FROM products WHERE id=? AND archived=0",(product_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404,detail="Product not found.")
            quantity=row["quantity"]+form.change
            if quantity<0:
                raise HTTPException(status_code=400,detail=f"Only {row['quantity']} units available; stock cannot go below zero.")
            if quantity>MAX_STOCK:
                raise HTTPException(status_code=400,detail="Stock exceeds the allowed maximum.")
            cn.execute("UPDATE products SET quantity=?,updated_at=? WHERE id=?",(quantity,local_time(),product_id))
            cn.execute("""INSERT INTO stock_movements
                (product_id,change_amount,reason,note,actor_id) VALUES (?,?,?,?,?)""",
                (product_id,form.change,form.reason,clean_str(form.note),current["id"]))
            cn.commit()
            return product_json(cn.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone())
        except Exception:
            cn.rollback()
            raise

    @api.get("/api/stock-movements")
    def stock_movements(limit:int=Query(default=100,ge=1,le=500),_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        rows=cn.execute("""SELECT m.id,m.product_id,p.name AS product_name,p.sku,m.change_amount,m.reason,m.note,
             COALESCE(u.email,'Demo data') AS actor,m.created_at FROM stock_movements m
             JOIN products p ON p.id=m.product_id LEFT JOIN users u ON u.id=m.actor_id
             ORDER BY m.created_at DESC,m.id DESC LIMIT ?""",(limit,)).fetchall()
        return {"movements":[dict(r) for r in rows]}

    @api.post("/api/sales",status_code=201)
    def make_sale(form:SaleIn,current=Depends(user),cn:sqlite3.Connection=Depends(db)):
        amounts:dict[int,int]={}
        for line in form.items:
            amounts[line.product_id]=amounts.get(line.product_id,0)+line.quantity
        if any(q>10000 for q in amounts.values()):
            raise HTTPException(status_code=422,detail="Too many units in one sale.")
        try:
            cn.execute("BEGIN IMMEDIATE")
            details=[]
            for prod_id,qty in amounts.items():
                prod=cn.execute("SELECT * FROM products WHERE id=? AND archived=0",(prod_id,)).fetchone()
                if prod is None:
                    raise HTTPException(status_code=404,detail=f"Product #{prod_id} is unavailable.")
                if prod["quantity"]<qty:
                    raise HTTPException(status_code=409,detail=f"Not enough stock for {prod['name']}. Only {prod['quantity']} left.")
                details.append((prod,qty))
            total=sum(p["price_cents"]*q for p,q in details)
            if total<=0:
                raise HTTPException(status_code=422,detail="A sale must have a positive total.")
            receipt=f"BS-{datetime.now():%y%m%d}-{secrets.token_hex(3).upper()}"
            sale_id=cn.execute("INSERT INTO sales(receipt_no,total_cents,payment_method,actor_id) VALUES (?,?,?,?)",
                (receipt,total,form.payment_method,current["id"])).lastrowid
            for p,q in details:
                cn.execute("""INSERT INTO sale_items
                    (sale_id,product_id,product_name,quantity,unit_price_cents,unit_cost_cents,line_total_cents)
                    VALUES (?,?,?,?,?,?,?)""",
                    (sale_id,p["id"],p["name"],q,p["price_cents"],p["cost_cents"],p["price_cents"]*q))
                cn.execute("UPDATE products SET quantity=quantity-?,updated_at=? WHERE id=?",(q,local_time(),p["id"]))
                cn.execute("""INSERT INTO stock_movements
                    (product_id,change_amount,reason,note,actor_id) VALUES (?,?,?,?,?)""",
                    (p["id"],-q,"Sale",receipt,current["id"]))
            cn.commit()
            return {"sale_id":sale_id,"receipt_no":receipt,"total":total/100,"items":len(details),"payment_method":form.payment_method}
        except Exception:
            cn.rollback()
            raise

    @api.get("/api/sales")
    def sales(q:str="",limit:int=Query(default=100,ge=1,le=500),_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        rows=cn.execute("""SELECT s.id,s.receipt_no,s.total_cents,s.payment_method,s.created_at,
            COUNT(si.id) AS distinct_items,COALESCE(SUM(si.quantity),0) AS units,
            COALESCE(GROUP_CONCAT(si.product_name || ' ×' || si.quantity, ', '),'') AS description
            FROM sales s LEFT JOIN sale_items si ON s.id=si.sale_id
            WHERE s.receipt_no LIKE ? GROUP BY s.id ORDER BY s.created_at DESC,s.id DESC LIMIT ?""",
            (f"%{q.strip()[:50]}%",limit)).fetchall()
        return {"sales":[{**dict(r),"total":r["total_cents"]/100} for r in rows]}

    def date_series(cn:sqlite3.Connection,days:int) -> list[dict]:
        lower=(datetime.now()-timedelta(days=days-1)).strftime("%Y-%m-%d")
        rows=cn.execute("""SELECT date(created_at) AS day, SUM(total_cents) AS revenue_cents,
           COUNT(*) AS orders FROM sales WHERE date(created_at)>=? GROUP BY date(created_at)""",(lower,)).fetchall()
        by_day={r["day"]:r for r in rows}
        return [{"day":(datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d"),
                 "revenue":round(by_day[(datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")]["revenue_cents"]/100,2) if (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d") in by_day else 0,
                 "orders":by_day[(datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d")]["orders"] if (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d") in by_day else 0}
                for i in range(days-1,-1,-1)]

    @api.get("/api/overview")
    def overview(_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        metrics=cn.execute("""SELECT COUNT(*) AS total_products,COALESCE(SUM(quantity),0) AS units,
            COALESCE(SUM(CASE WHEN quantity>0 AND quantity<=min_stock THEN 1 ELSE 0 END),0) AS low_stock,
            COALESCE(SUM(CASE WHEN quantity=0 THEN 1 ELSE 0 END),0) AS out_stock,
            COALESCE(SUM(CASE WHEN quantity>min_stock THEN 1 ELSE 0 END),0) AS healthy
            FROM products WHERE archived=0""").fetchone()
        today=cn.execute("SELECT COALESCE(SUM(total_cents),0) AS total,COUNT(*) AS orders FROM sales WHERE date(created_at)=date('now','localtime')").fetchone()
        alert_rows=cn.execute("SELECT * FROM products WHERE archived=0 AND quantity<=min_stock ORDER BY quantity ASC LIMIT 8").fetchall()
        latest=cn.execute("""SELECT receipt_no,total_cents,payment_method,created_at FROM sales
            ORDER BY created_at DESC,id DESC LIMIT 6""").fetchall()
        return {"metrics":{**dict(metrics),"today_sales":today["total"]/100,"today_orders":today["orders"]},
                "chart":date_series(cn,7),"alerts":[product_json(r) for r in alert_rows],
                "recent_sales":[{**dict(r),"total":r["total_cents"]/100} for r in latest]}

    @api.get("/api/reports")
    def reports(days: int = Query(default=30),_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        lower=(datetime.now()-timedelta(days=days-1)).strftime("%Y-%m-%d")
        main=cn.execute("""SELECT COUNT(*) AS orders,COALESCE(SUM(total_cents),0) AS revenue_cents
            FROM sales WHERE date(created_at)>=?""",(lower,)).fetchone()
        costs=cn.execute("""SELECT COALESCE(SUM(si.unit_cost_cents*si.quantity),0) AS cogs_cents,
            COALESCE(SUM(si.quantity),0) AS units FROM sale_items si
            JOIN sales s ON s.id=si.sale_id WHERE date(s.created_at)>=?""",(lower,)).fetchone()
        tops=cn.execute("""SELECT si.product_name AS name, SUM(si.quantity) AS units,
            SUM(si.line_total_cents) AS revenue_cents FROM sale_items si
            JOIN sales s ON s.id=si.sale_id WHERE date(s.created_at)>=?
            GROUP BY si.product_id ORDER BY units DESC LIMIT 6""",(lower,)).fetchall()
        categories=cn.execute("""SELECT p.category, SUM(si.line_total_cents) AS revenue_cents
            FROM sale_items si JOIN products p ON p.id=si.product_id
            JOIN sales s ON s.id=si.sale_id WHERE date(s.created_at)>=?
            GROUP BY p.category ORDER BY revenue_cents DESC""",(lower,)).fetchall()
        return {"days":days,"orders":main["orders"],"revenue":main["revenue_cents"]/100,
                "cogs":costs["cogs_cents"]/100,"profit":(main["revenue_cents"]-costs["cogs_cents"])/100,
                "units_sold":costs["units"],"chart":date_series(cn,days),
                "top_products":[{**dict(r),"revenue":r["revenue_cents"]/100} for r in tops],
                "categories":[{"category":r["category"],"revenue":r["revenue_cents"]/100} for r in categories]}

    @api.get("/api/insights")
    def insights(_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        rows=cn.execute("""SELECT p.*,COALESCE(SUM(CASE WHEN s.created_at >= ? THEN si.quantity ELSE 0 END),0) AS sold14
             FROM products p LEFT JOIN sale_items si ON si.product_id=p.id
             LEFT JOIN sales s ON s.id=si.sale_id WHERE p.archived=0
             GROUP BY p.id ORDER BY p.quantity ASC""",
             ((datetime.now()-timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()
        recs=[]
        for r in rows:
            sold=int(r["sold14"] or 0)
            avg=sold/14
            target=max(r["min_stock"]*2, math.ceil(avg*7)+r["min_stock"])
            recommendation=max(0,target-r["quantity"])
            if r["quantity"]<=r["min_stock"]:
                recs.append({**product_json(r),"sold14":sold,"avg_daily":round(avg,1),
                             "recommended_order":recommendation,"target_stock":target,
                             "priority":"Urgent" if r["quantity"]==0 else "Reorder"})
        return {"recommendations":recs,"method":"Rule-based, not machine learning. Suggested order = max(2 × minimum stock, 7-day demand + minimum stock) − current stock. Daily demand = units sold in past 14 days ÷ 14. This is an estimate; review before purchasing."}

    @api.get("/api/export/products")
    def export_products(_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        rows=cn.execute("SELECT * FROM products WHERE archived=0 ORDER BY name").fetchall()
        output=io.StringIO()
        writer=csv.writer(output)
        writer.writerow(["SKU","Name","Category","Price PHP","Cost PHP","Quantity","Minimum Stock","Unit","Status"])
        def safe(text):
            val=str(text)
            return "'"+val if val.startswith(("=","+","-","@","\t","\r","\n")) else val
        for row in rows:
            p=product_json(row)
            writer.writerow([safe(p["sku"]),safe(p["name"]),safe(p["category"]),f"{p['price']:.2f}",f"{p['cost']:.2f}",p["quantity"],p["min_stock"],p["unit"],p["status"]])
        return Response(content="\ufeff"+output.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=breadstore-products.csv"})

    @api.get("/api/export/sales")
    def export_sales(_=Depends(user),cn:sqlite3.Connection=Depends(db)):
        rows=cn.execute("""SELECT s.receipt_no,s.created_at,s.payment_method,si.product_name,si.quantity,
            si.unit_price_cents,si.line_total_cents FROM sale_items si
            JOIN sales s ON s.id=si.sale_id ORDER BY s.created_at DESC,s.id DESC""").fetchall()
        output=io.StringIO()
        writer=csv.writer(output)
        writer.writerow(["Receipt","Date","Payment","Product","Quantity","Unit Price PHP","Line Total PHP"])
        def safe(value):
            val=str(value)
            return "'"+val if val.startswith(("=","+","-","@","\t","\r","\n")) else val
        for r in rows:
            writer.writerow([safe(r["receipt_no"]),r["created_at"],safe(r["payment_method"]),safe(r["product_name"]),r["quantity"],f"{r['unit_price_cents']/100:.2f}",f"{r['line_total_cents']/100:.2f}"])
        return Response(content="\ufeff"+output.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=breadstore-sales.csv"})

    from customer_routes import install_customer_routes
    install_customer_routes(api, path, user, SESSION_SECONDS)
    return api


app = create_app()
