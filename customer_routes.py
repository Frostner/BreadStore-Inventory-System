"""Customer storefront APIs and order fulfillment for BreadStore.

Safe additive migrations preserve existing inventory, admin accounts and POS sales.
Stock is reserved atomically at order placement; a sale is recorded only once,
when an admin marks a pickup order completed.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import sqlite3
import time

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from database import connect, password_hash, verify_password

UPGRADE_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 full_name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL,
 salt TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS customer_sessions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE,
 expires_at TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_sessions ON customer_sessions(customer_id);
CREATE TABLE IF NOT EXISTS customer_orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 order_no TEXT NOT NULL UNIQUE,
 customer_id INTEGER NOT NULL REFERENCES customers(id),
 status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Preparing','Ready','Completed','Cancelled')),
 pickup_name TEXT NOT NULL,
 note TEXT NOT NULL DEFAULT '',
 total_cents INTEGER NOT NULL CHECK(total_cents > 0),
 sale_id INTEGER UNIQUE REFERENCES sales(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_orders_customer ON customer_orders(customer_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_orders_status ON customer_orders(status,created_at DESC);
CREATE TABLE IF NOT EXISTS customer_order_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 order_id INTEGER NOT NULL REFERENCES customer_orders(id) ON DELETE CASCADE,
 product_id INTEGER NOT NULL REFERENCES products(id),
 product_name TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity > 0),
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents > 0),
 unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents >= 0),
 line_total_cents INTEGER NOT NULL CHECK(line_total_cents > 0)
);
"""


def upgrade_database(path):
    with connect(path) as cn:
        cn.executescript(UPGRADE_SCHEMA)


def now_local():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def now_utc(offset=0):
    return (datetime.now(timezone.utc)+timedelta(seconds=offset)).strftime('%Y-%m-%d %H:%M:%S')


class RegisterForm(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=200)

    @field_validator('full_name')
    @classmethod
    def name_ok(cls, v):
        v=' '.join(v.strip().split())
        if len(v)<2:
            raise ValueError('Please enter your name.')
        return v

    @field_validator('email')
    @classmethod
    def email_ok(cls,v):
        v=v.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v):
            raise ValueError('Enter a valid email address.')
        return v


class CustomerLogin(BaseModel):
    email: str = Field(min_length=5,max_length=255)
    password: str = Field(min_length=1,max_length=200)


class OrderLine(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1,le=10000)


class NewOrder(BaseModel):
    items: list[OrderLine] = Field(min_length=1,max_length=40)
    pickup_name: str = Field(min_length=2,max_length=80)
    note: str = Field(default='',max_length=250)

    @field_validator('pickup_name')
    @classmethod
    def pickup_ok(cls,v):
        v=' '.join(v.strip().split())
        if len(v)<2:
            raise ValueError('Please enter a pickup name.')
        return v


class ChangeOrderStatus(BaseModel):
    status: str


def as_order(cn, row):
    items=cn.execute('''SELECT product_id,product_name,quantity,unit_price_cents,line_total_cents
          FROM customer_order_items WHERE order_id=? ORDER BY id''',(row['id'],)).fetchall()
    obj={k:row[k] for k in ('id','order_no','status','pickup_name','note','created_at','updated_at')}
    obj['total']=row['total_cents']/100
    obj['items']=[{'product_id':r['product_id'],'name':r['product_name'],'quantity':r['quantity'],
                   'unit_price':r['unit_price_cents']/100,'line_total':r['line_total_cents']/100} for r in items]
    if 'customer_name' in row.keys():
        obj['customer_name']=row['customer_name']
        obj['customer_email']=row['customer_email']
    return obj


def install_customer_routes(api,path, admin_auth, secure_seconds=43200):
    """Register storefront, customer session and admin order APIs."""
    upgrade_database(path)

    def db():
        cn=connect(path)
        try: yield cn
        finally: cn.close()

    def customer(request:Request,cn:sqlite3.Connection=Depends(db)):
        token=request.cookies.get('breadstore_customer','')
        if len(token)<20:
            raise HTTPException(status_code=401,detail='Please sign in to place orders.')
        row=cn.execute('''SELECT c.id,c.full_name,c.email FROM customer_sessions s
            JOIN customers c ON c.id=s.customer_id WHERE s.token_hash=? AND s.expires_at>?''',
            (hashlib.sha256(token.encode()).hexdigest(),now_utc())).fetchone()
        if row is None:
            raise HTTPException(status_code=401,detail='Customer session expired. Please sign in again.')
        return dict(row)

    def new_cookie(request, customer_row,cn,status_code=200):
        raw=secrets.token_urlsafe(32)
        with cn:
            cn.execute('DELETE FROM customer_sessions WHERE expires_at<=?',(now_utc(),))
            cn.execute('INSERT INTO customer_sessions(customer_id,token_hash,expires_at) VALUES (?,?,?)',
                       (customer_row['id'],hashlib.sha256(raw.encode()).hexdigest(),now_utc(secure_seconds)))
        resp=JSONResponse({'id':customer_row['id'],'full_name':customer_row['full_name'],'email':customer_row['email']},status_code=status_code)
        import os
        secure=os.getenv('COOKIE_SECURE','false').lower()=='true' or request.url.scheme=='https'
        resp.set_cookie('breadstore_customer',raw,max_age=secure_seconds,path='/',httponly=True,samesite='strict',secure=secure)
        return resp

    @api.get('/shop')
    @api.get('/shop/')
    def storefront():
        return FileResponse(str(__import__('pathlib').Path(__file__).resolve().parent/'static'/'shop.html'))

    @api.get('/api/shop/products')
    def public_products(q:str=Query(default='',max_length=100),cn:sqlite3.Connection=Depends(db)):
        like='%'+q.strip()+'%'
        rows=cn.execute('''SELECT id,sku,name,category,price_cents,quantity,unit FROM products
            WHERE archived=0 AND (name LIKE ? OR category LIKE ? OR sku LIKE ?)
            ORDER BY category,name''',(like,like,like)).fetchall()
        return {'products':[{'id':r['id'],'sku':r['sku'],'name':r['name'],'category':r['category'],
             'price':r['price_cents']/100,'stock':r['quantity'],'unit':r['unit']} for r in rows]}

    @api.post('/api/shop/register',status_code=201)
    def register(form:RegisterForm,request:Request,cn:sqlite3.Connection=Depends(db)):
        key='register:'+(request.client.host if request.client else 'unknown')
        t=time.monotonic()
        attempts=[x for x in api.state.login_attempts.get(key,[]) if t-x<600]
        if len(attempts)>=12:
            raise HTTPException(status_code=429,detail='Too many registrations. Try again later.')
        api.state.login_attempts[key]=attempts+[t]
        digest,salt=password_hash(form.password)
        try:
            with cn:
                result=cn.execute('INSERT INTO customers(full_name,email,password_hash,salt) VALUES (?,?,?,?)',
                    (form.full_name,form.email,digest,salt))
            row=cn.execute('SELECT id,full_name,email FROM customers WHERE id=?',(result.lastrowid,)).fetchone()
            return new_cookie(request,row,cn,status_code=201)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409,detail='This email is already registered. Please sign in.')

    @api.post('/api/shop/login')
    def shop_login(form:CustomerLogin,request:Request,cn:sqlite3.Connection=Depends(db)):
        key='customer-login:'+(request.client.host if request.client else 'unknown')
        t=time.monotonic()
        attempts=[x for x in api.state.login_attempts.get(key,[]) if t-x<600]
        if len(attempts)>=10:
            raise HTTPException(status_code=429,detail='Too many attempts. Try again in 10 minutes.')
        row=cn.execute('SELECT * FROM customers WHERE email=?',(form.email.strip().lower(),)).fetchone()
        if row:
            valid=verify_password(form.password,row['password_hash'],row['salt'])
        else:
            password_hash(form.password,'0'*32)
            valid=False
        if not valid:
            api.state.login_attempts[key]=attempts+[t]
            raise HTTPException(status_code=401,detail='Incorrect email or password.')
        api.state.login_attempts.pop(key,None)
        return new_cookie(request,row,cn)

    @api.get('/api/shop/me')
    def shop_me(c=Depends(customer)):
        return c

    @api.post('/api/shop/logout')
    def shop_logout(request:Request,c=Depends(customer),cn:sqlite3.Connection=Depends(db)):
        raw=request.cookies.get('breadstore_customer','')
        with cn:
            cn.execute('DELETE FROM customer_sessions WHERE token_hash=?',(hashlib.sha256(raw.encode()).hexdigest(),))
        resp=JSONResponse({'message':'Signed out.'})
        resp.delete_cookie('breadstore_customer',path='/')
        return resp

    @api.post('/api/shop/orders',status_code=201)
    def place_order(form:NewOrder,c=Depends(customer),cn:sqlite3.Connection=Depends(db)):
        amounts={}
        for line in form.items:
            amounts[line.product_id]=amounts.get(line.product_id,0)+line.quantity
        if any(q>10000 for q in amounts.values()):
            raise HTTPException(status_code=422,detail='Too many units of one product in the order.')
        try:
            cn.execute('BEGIN IMMEDIATE')
            products=[]
            for prod_id,quantity in amounts.items():
                row=cn.execute('SELECT * FROM products WHERE id=? AND archived=0',(prod_id,)).fetchone()
                if not row:
                    raise HTTPException(status_code=404,detail=f'Product #{prod_id} is no longer available.')
                if row['quantity']<quantity:
                    raise HTTPException(status_code=409,detail=f"Not enough {row['name']} in stock (only {row['quantity']} left).")
                products.append((row,quantity))
            total=sum(p['price_cents']*qty for p,qty in products)
            if total<=0:
                raise HTTPException(status_code=422,detail='An order must have a positive total.')
            order_no=f"BK-{datetime.now():%y%m%d}-{secrets.token_hex(4).upper()}"
            result=cn.execute('''INSERT INTO customer_orders(order_no,customer_id,pickup_name,note,total_cents)
                        VALUES (?,?,?,?,?)''',(order_no,c['id'],form.pickup_name,' '.join(form.note.strip().split()),total))
            order_id=result.lastrowid
            for p,qty in products:
                cn.execute('''INSERT INTO customer_order_items(order_id,product_id,product_name,quantity,
                            unit_price_cents,unit_cost_cents,line_total_cents) VALUES(?,?,?,?,?,?,?)''',
                           (order_id,p['id'],p['name'],qty,p['price_cents'],p['cost_cents'],qty*p['price_cents']))
                cn.execute('UPDATE products SET quantity=quantity-?,updated_at=? WHERE id=?',
                           (qty,now_local(),p['id']))
                cn.execute('''INSERT INTO stock_movements(product_id,change_amount,reason,note)
                              VALUES (?,?,?,?)''',(p['id'],-qty,'Online order reservation',order_no))
            cn.commit()
            return {'order_no':order_no,'status':'Pending','total':total/100,'order_id':order_id,
                    'message':'Order received. Please wait for the bakery to confirm pickup readiness. Pay at pickup.'}
        except Exception:
            cn.rollback()
            raise

    @api.get('/api/shop/orders')
    def my_orders(c=Depends(customer),cn:sqlite3.Connection=Depends(db)):
        rows=cn.execute('SELECT * FROM customer_orders WHERE customer_id=? ORDER BY id DESC',(c['id'],)).fetchall()
        return {'orders':[as_order(cn,row) for row in rows]}

    def cancel_order(cn,row,actor_id=None):
        lines=cn.execute('SELECT product_id,quantity FROM customer_order_items WHERE order_id=?',(row['id'],)).fetchall()
        for line in lines:
            cn.execute('UPDATE products SET quantity=quantity+?,updated_at=? WHERE id=?',
                       (line['quantity'],now_local(),line['product_id']))
            cn.execute('''INSERT INTO stock_movements(product_id,change_amount,reason,note,actor_id)
                   VALUES (?,?,?,?,?)''',(line['product_id'],line['quantity'],'Online order cancelled',row['order_no'],actor_id))
        cn.execute('UPDATE customer_orders SET status=?,updated_at=? WHERE id=?',('Cancelled',now_local(),row['id']))

    @api.post('/api/shop/orders/{order_id}/cancel')
    def my_cancel(order_id:int,c=Depends(customer),cn:sqlite3.Connection=Depends(db)):
        try:
            cn.execute('BEGIN IMMEDIATE')
            row=cn.execute('SELECT * FROM customer_orders WHERE id=? AND customer_id=?',(order_id,c['id'])).fetchone()
            if row is None:
                raise HTTPException(status_code=404,detail='Order not found.')
            if row['status']!='Pending':
                raise HTTPException(status_code=409,detail='Only pending orders can be cancelled online. Contact the bakery.')
            cancel_order(cn,row)
            cn.commit()
            return {'message':'Order cancelled and stock returned.'}
        except Exception:
            cn.rollback()
            raise

    @api.get('/api/customer-orders')
    def admin_orders(status:str='All',q:str='',_=Depends(admin_auth),cn:sqlite3.Connection=Depends(db)):
        args=[]
        where=[]
        if status!='All':
            where.append('o.status=?');args.append(status)
        if q.strip():
            where.append('(o.order_no LIKE ? OR c.full_name LIKE ? OR c.email LIKE ?)')
            args.extend(['%'+q.strip()[:100]+'%']*3)
        clause=('WHERE '+' AND '.join(where)) if where else ''
        rows=cn.execute('''SELECT o.*,c.full_name AS customer_name,c.email AS customer_email
             FROM customer_orders o JOIN customers c ON c.id=o.customer_id '''+clause+
             ' ORDER BY CASE WHEN o.status IN (\'Pending\',\'Preparing\',\'Ready\') THEN 0 ELSE 1 END, o.id DESC LIMIT 250',args).fetchall()
        return {'orders':[as_order(cn,row) for row in rows]}

    @api.patch('/api/customer-orders/{order_id}')
    def update_order(order_id:int,form:ChangeOrderStatus,admin=Depends(admin_auth),cn:sqlite3.Connection=Depends(db)):
        transitions={'Pending':{'Preparing','Cancelled'},'Preparing':{'Ready','Cancelled'},
                     'Ready':{'Completed','Cancelled'},'Completed':set(),'Cancelled':set()}
        try:
            cn.execute('BEGIN IMMEDIATE')
            row=cn.execute('SELECT * FROM customer_orders WHERE id=?',(order_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404,detail='Order not found.')
            if form.status not in transitions[row['status']]:
                raise HTTPException(status_code=409,detail=f"Cannot change an order from {row['status']} to {form.status}.")
            if form.status=='Cancelled':
                cancel_order(cn,row,actor_id=admin['id'])
            elif form.status=='Completed':
                # Reserved stock was already subtracted during checkout. Do not deduct twice.
                sale_receipt='WEB-'+row['order_no']
                sale=cn.execute('''INSERT INTO sales(receipt_no,total_cents,payment_method,actor_id)
                             VALUES(?,?,?,?)''',(sale_receipt,row['total_cents'],'Pay at pickup',admin['id']))
                items=cn.execute('SELECT * FROM customer_order_items WHERE order_id=?',(order_id,)).fetchall()
                for item in items:
                    cn.execute('''INSERT INTO sale_items(sale_id,product_id,product_name,quantity,
                       unit_price_cents,unit_cost_cents,line_total_cents) VALUES(?,?,?,?,?,?,?)''',
                       (sale.lastrowid,item['product_id'],item['product_name'],item['quantity'],
                        item['unit_price_cents'],item['unit_cost_cents'],item['line_total_cents']))
                cn.execute('UPDATE customer_orders SET status=?,sale_id=?,updated_at=? WHERE id=?',
                           ('Completed',sale.lastrowid,now_local(),order_id))
            else:
                cn.execute('UPDATE customer_orders SET status=?,updated_at=? WHERE id=?',
                           (form.status,now_local(),order_id))
            cn.commit()
            return {'message':'Order updated.','status':form.status}
        except Exception:
            cn.rollback()
            raise
