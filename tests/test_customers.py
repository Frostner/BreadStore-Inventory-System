"""End-to-end API tests for customer registration, ordering and admin fulfillment."""
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app import create_app

H={'X-Requested-With':'BreadStore'}
ADMIN_PASSWORD='SecureAdminPassword1234!'
CUSTOMER_PASSWORD='SecureCustomerPassword1234!'

def setup(tmp):
    os.environ['ADMIN_EMAIL']='admin@test.local'
    os.environ['ADMIN_PASSWORD']=ADMIN_PASSWORD
    return TestClient(create_app(Path(tmp)/'store.db',demo=False))

def admin_login(c):
    r=c.post('/api/auth/login',headers=H,json={'email':'admin@test.local','password':ADMIN_PASSWORD})
    assert r.status_code==200,r.text

def create_product(c,stock=10):
    admin_login(c)
    r=c.post('/api/products',headers=H,json={'sku':'B-100','name':'Cheese Pandesal','category':'Everyday Bread',
         'price':15,'cost':8,'quantity':stock,'min_stock':3,'unit':'pcs'})
    assert r.status_code==201,r.text
    return r.json()['id']

def register(c,email='customer@example.com'):
    r=c.post('/api/shop/register',headers=H,json={'full_name':'Alex Customer','email':email,'password':CUSTOMER_PASSWORD})
    assert r.status_code==201,r.text
    return r.json()

def order(c,id,qty=2):
    return c.post('/api/shop/orders',headers=H,json={'pickup_name':'Alex Customer','note':'Please pack separately',
              'items':[{'product_id':id,'quantity':qty}]})


def test_public_storefront_customer_registration_and_separation():
    with TemporaryDirectory() as tmp,setup(tmp) as c:
        assert c.get('/shop').status_code==200
        assert 'BreadStore' in c.get('/shop').text
        assert c.get('/api/shop/products').json()=={'products':[]}
        assert c.get('/api/customer-orders').status_code==401
        assert c.get('/api/shop/orders').status_code==401
        bad=c.post('/api/shop/register',headers=H,json={'full_name':'A','email':'not-email','password':'tiny'})
        assert bad.status_code==422
        register(c)
        assert c.get('/api/shop/me').json()['full_name']=='Alex Customer'
        assert c.get('/api/products').status_code==401 # customer cookie is not admin auth
        assert c.get('/api/customer-orders').status_code==401
        assert c.post('/api/shop/register',headers=H,json={'full_name':'Other User','email':'CUSTOMER@example.com','password':CUSTOMER_PASSWORD}).status_code==409
        assert c.post('/api/shop/logout',headers=H).status_code==200
        assert c.get('/api/shop/me').status_code==401
        assert c.post('/api/shop/login',headers=H,json={'email':'customer@example.com','password':'bad'}).status_code==401
        assert c.post('/api/shop/login',headers=H,json={'email':'customer@example.com','password':CUSTOMER_PASSWORD}).status_code==200


def test_orders_reserve_stock_and_cancel_without_sales():
    with TemporaryDirectory() as tmp,setup(tmp) as c:
        pid=create_product(c,stock=6)
        public=c.get('/api/shop/products').json()['products'][0]
        assert public['stock']==6 and public['price']==15
        assert 'cost' not in public and 'min_stock' not in public
        register(c)
        assert order(c,pid,qty=7).status_code==409
        assert c.get('/api/shop/products').json()['products'][0]['stock']==6
        accepted=order(c,pid,qty=4)
        assert accepted.status_code==201,accepted.text
        assert accepted.json()['total']==60
        assert c.get('/api/shop/products').json()['products'][0]['stock']==2
        assert c.get('/api/shop/orders').json()['orders'][0]['status']=='Pending'
        order_id=accepted.json()['order_id']
        assert c.get('/api/sales').json()['sales']==[]
        assert c.post(f'/api/shop/orders/{order_id}/cancel',headers=H).status_code==200
        assert c.post(f'/api/shop/orders/{order_id}/cancel',headers=H).status_code==409
        assert c.get('/api/shop/products').json()['products'][0]['stock']==6
        assert c.get('/api/sales').json()['sales']==[]


def test_order_fulfillment_makes_exactly_one_sale_and_preserves_snapshot():
    with TemporaryDirectory() as tmp,setup(tmp) as c:
        pid=create_product(c,stock=8)
        register(c)
        data=order(c,pid,qty=3).json()
        oid=data['order_id']
        assert c.get('/api/shop/products').json()['products'][0]['stock']==5
        admin_orders=c.get('/api/customer-orders').json()['orders']
        assert len(admin_orders)==1 and admin_orders[0]['customer_email']=='customer@example.com'
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Completed'}).status_code==409
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Preparing'}).status_code==200
        assert c.post(f'/api/shop/orders/{oid}/cancel',headers=H).status_code==409
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Ready'}).status_code==200
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Completed'}).status_code==200
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Completed'}).status_code==409
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Cancelled'}).status_code==409
        assert c.get('/api/shop/products').json()['products'][0]['stock']==5
        sales=c.get('/api/sales').json()['sales']
        assert len(sales)==1 and sales[0]['total']==45
        assert sales[0]['payment_method']=='Pay at pickup'
        assert c.get('/api/reports?days=7').json()['revenue']==45
        assert c.get('/api/shop/orders').json()['orders'][0]['status']=='Completed'
        with sqlite3.connect(str(Path(tmp)/'store.db')) as db:
            assert db.execute('select count(*) from customer_order_items').fetchone()[0]==1
            assert db.execute('select count(*) from sale_items').fetchone()[0]==1


def test_customer_isolation_cancel_permission_and_atomic_funds():
    with TemporaryDirectory() as tmp,setup(tmp) as c:
        pid=create_product(c,stock=10)
        assert c.post('/api/auth/logout',headers=H).status_code==200
        register(c)
        oid=order(c,pid).json()['order_id']
        c.post('/api/shop/logout',headers=H)
        register(c,'another@example.com')
        assert c.get('/api/shop/orders').json()['orders']==[]
        assert c.post(f'/api/shop/orders/{oid}/cancel',headers=H).status_code==404
        assert c.post('/api/shop/orders',headers=H,json={'pickup_name':'Alex',
               'items':[{'product_id':pid,'quantity':10000},{'product_id':pid,'quantity':10000}]}).status_code==422
        assert c.get('/api/shop/products').json()['products'][0]['stock']==8
        # A customer can never call staff fulfillment APIs.
        assert c.patch(f'/api/customer-orders/{oid}',headers=H,json={'status':'Ready'}).status_code==401


def test_upgrading_existing_database_is_non_destructive():
    with TemporaryDirectory() as tmp:
        dbpath=Path(tmp)/'existing.db'
        from database import initialize,connect
        os.environ['ADMIN_EMAIL']='admin@test.local';os.environ['ADMIN_PASSWORD']=ADMIN_PASSWORD
        initialize(dbpath,demo=False)
        with connect(dbpath) as db:
            db.execute("INSERT INTO products(sku,name,category,price_cents,cost_cents,quantity,min_stock,unit) VALUES ('X-1','Original Bread','Bread',1200,600,5,1,'pcs')")
        app=create_app(dbpath,demo=False)
        with TestClient(app) as c:
            assert c.get('/api/shop/products').json()['products'][0]['name']=='Original Bread'
            assert c.get('/api/health').json()['database']=='connected'
            admin_login(c)
            assert c.get('/api/products').json()['products'][0]['quantity']==5
            register(c)
            assert order(c,1).status_code==201
