"""Integration tests: exercise the real FastAPI endpoints against temp SQLite databases.
Run: python -m pytest -q
"""
import os
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
from app import create_app

PASSWORD = 'CorrectPasswordForTests123!'
HEADERS = {'X-Requested-With':'BreadStore'}


def client():
    tmp = tempfile.TemporaryDirectory()
    os.environ['ADMIN_EMAIL']='test@example.com'
    os.environ['ADMIN_PASSWORD']=PASSWORD
    app = create_app(Path(tmp.name)/'test.db', demo=False)
    c = TestClient(app)
    c._temp_directory = tmp
    return c


def login(c):
    response=c.post('/api/auth/login',json={'email':'test@example.com','password':PASSWORD},headers=HEADERS)
    assert response.status_code==200,response.text


def product(code='B-001',stock=10,name='Warm Pandesal'):
    return {'sku':code,'name':name,'category':'Everyday Bread','price':15.50,'cost':6.30,'min_stock':3,'quantity':stock,'unit':'pcs'}


def add(c,p=None):
    res=c.post('/api/products',json=p or product(),headers=HEADERS)
    assert res.status_code==201,res.text
    return res.json()


def test_database_health_and_protection():
    with client() as c:
        assert c.get('/api/health').json()['database']=='connected'
        assert c.get('/api/products').status_code==401
        assert c.post('/api/auth/login',json={'email':'test@example.com','password':PASSWORD}).status_code==403
        assert c.post('/api/auth/login',json={'email':'test@example.com','password':'wrong'},headers=HEADERS).status_code==401
        login(c)
        assert c.get('/api/auth/me').json()['role']=='Administrator'
        assert c.get('/api/products').json()['products']==[]
        assert c.post('/api/auth/logout',headers=HEADERS).status_code==200
        assert c.get('/api/products').status_code==401


def test_crud_search_archive_and_restore():
    with client() as c:
        login(c)
        p=add(c)
        assert p['quantity']==10 and p['status']=='In stock'
        assert c.get('/api/products?q=pandesal').json()['products'][0]['sku']=='B-001'
        assert len(c.get('/api/products?q=does_not_exist').json()['products'])==0
        dup=c.post('/api/products',json=product(),headers=HEADERS)
        assert dup.status_code==409
        updated={k:v for k,v in product().items() if k!='quantity'}
        updated['name']='Fresh Pandesal'
        updated['price']=20.00
        changed=c.put(f'/api/products/{p["id"]}',json=updated,headers=HEADERS)
        assert changed.status_code==200 and changed.json()['price']==20
        assert c.delete(f'/api/products/{p["id"]}',headers=HEADERS).status_code==200
        assert len(c.get('/api/products').json()['products'])==0
        assert len(c.get('/api/products?status=Archived').json()['products'])==1
        assert c.post(f'/api/products/{p["id"]}/restore',headers=HEADERS).status_code==200
        assert len(c.get('/api/products').json()['products'])==1


def test_input_validation_and_stock_adjustments():
    with client() as c:
        login(c)
        bad=product()
        bad['price']=-10
        assert c.post('/api/products',json=bad,headers=HEADERS).status_code==422
        bad=product()
        bad['sku']=' x; drop table products --'
        assert c.post('/api/products',json=bad,headers=HEADERS).status_code==422
        p=add(c)
        res=c.post(f'/api/products/{p["id"]}/adjust',headers=HEADERS,json={'change':5,'reason':'Restock','note':'morning delivery'})
        assert res.status_code==200 and res.json()['quantity']==15
        res=c.post(f'/api/products/{p["id"]}/adjust',headers=HEADERS,json={'change':-100,'reason':'Damage / waste','note':'bad batch'})
        assert res.status_code==400
        assert c.get('/api/products').json()['products'][0]['quantity']==15
        history=c.get('/api/stock-movements').json()['movements']
        assert any(m['reason']=='Restock' and m['change_amount']==5 for m in history)


def test_sales_atomic_inventory_deduction_and_price_snapshot():
    with client() as c:
        login(c)
        a=add(c,product(code='B-A',stock=8))
        b=add(c,product(code='B-B',stock=1,name='Ube Bun'))
        before=c.get('/api/overview').json()['metrics']['units']
        fail=c.post('/api/sales',headers=HEADERS,json={'payment_method':'GCash','items':[{'product_id':a['id'],'quantity':2},{'product_id':b['id'],'quantity':3}]})
        assert fail.status_code==409
        assert c.get('/api/overview').json()['metrics']['units']==before
        assert c.get('/api/sales').json()['sales']==[]
        success=c.post('/api/sales',headers=HEADERS,json={'payment_method':'GCash','items':[{'product_id':a['id'],'quantity':2},{'product_id':b['id'],'quantity':1}]})
        assert success.status_code==201, success.text
        assert success.json()['total']==46.50
        stocks={p['sku']:p['quantity'] for p in c.get('/api/products').json()['products']}
        assert stocks=={'B-A':6,'B-B':0}
        assert c.get('/api/overview').json()['metrics']['units']==before-3
        assert c.get('/api/overview').json()['metrics']['out_stock']==1
        rows=c.get('/api/sales').json()['sales']
        assert len(rows)==1 and rows[0]['units']==3
        assert c.get('/api/reports?days=7').json()['revenue']==46.50
        assert c.get('/api/reports?days=7').json()['profit']==27.60
        assert c.delete(f'/api/products/{a["id"]}',headers=HEADERS).status_code==200
        assert c.get('/api/sales').json()['sales'][0]['total']==46.50


def test_recommendations_csv_and_password_change():
    with client() as c:
        login(c)
        p=add(c,product(stock=2))
        insights=c.get('/api/insights').json()
        assert insights['recommendations'][0]['recommended_order']>=4
        assert 'not machine learning' in insights['method']
        csv=c.get('/api/export/products')
        assert csv.status_code==200 and 'Warm Pandesal' in csv.text
        assert 'text/csv' in csv.headers['content-type']
        bad=c.post('/api/auth/change-password',headers=HEADERS,json={'current_password':'wrong','new_password':'DifferentPassword123!'});
        assert bad.status_code==400
        changed=c.post('/api/auth/change-password',headers=HEADERS,json={'current_password':PASSWORD,'new_password':'DifferentPassword123!'})
        assert changed.status_code==200
        assert c.get('/api/auth/me').status_code==200
        c.post('/api/auth/logout',headers=HEADERS)
        assert c.post('/api/auth/login',headers=HEADERS,json={'email':'test@example.com','password':PASSWORD}).status_code==401
        assert c.post('/api/auth/login',headers=HEADERS,json={'email':'test@example.com','password':'DifferentPassword123!'}).status_code==200


def test_no_active_products_returned_when_all_archived():
    with client() as c:
        login(c)
        for i in range(3):
            p=add(c,product(code=f'BR-{i}',name=f'Bread Product {i}'))
            assert c.delete(f'/api/products/{p["id"]}',headers=HEADERS).status_code==200
        assert c.get('/api/overview').json()['metrics']['total_products']==0
        assert len(c.get('/api/products?status=Archived').json()['products'])==3
