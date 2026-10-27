'use strict';
const shop={products:[],category:'All treats',q:'',cart:{},customer:null,modal:null};
const el=s=>document.querySelector(s);
const money=n=>new Intl.NumberFormat('en-PH',{style:'currency',currency:'PHP'}).format(n);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Golden Crust product photography — images are packaged with the website and work offline.
const GC_PHOTOS_BY_SKU = {
  'BRD-001':'classic-pandesal.jpg',
  'BRD-002':'ube-cheese-pandesal.jpg',
  'BRD-003':'spanish-bread.jpg',
  'BRD-004':'cheese-roll.jpg',
  'BRD-005':'ensaymada.jpg',
  'BRD-006':'butter-croissant.jpg',
  'BRD-007':'chocolate-croissant.jpg',
  'BRD-008':'cinnamon-roll.jpg',
  'BRD-009':'banana-bread-slice.jpg',
  'BRD-010':'milk-bread-loaf.jpg',
  'BRD-011':'sourdough-loaf.jpg',
  'BRD-012':'garlic-baguette.jpg',
  'BRD-013':'strawberry-danish.jpg',
};
const GC_PHOTOS_BY_NAME = {
  'classic pandesal':'classic-pandesal.jpg',
  'ube cheese pandesal':'ube-cheese-pandesal.jpg',
  'spanish bread':'spanish-bread.jpg',
  'cheese roll':'cheese-roll.jpg',
  'ensaymada':'ensaymada.jpg',
  'butter croissant':'butter-croissant.jpg',
  'chocolate croissant':'chocolate-croissant.jpg',
  'cinnamon roll':'cinnamon-roll.jpg',
  'banana bread slice':'banana-bread-slice.jpg',
  'milk bread loaf':'milk-bread-loaf.jpg',
  'sourdough loaf':'sourdough-loaf.jpg',
  'garlic baguette':'garlic-baguette.jpg',
  'strawberry danish':'strawberry-danish.jpg',
};
const productPhoto = p => {
 const sku=String(p?.sku||'').trim().toUpperCase();
 const name=String(p?.name||'').trim().toLowerCase().replace(/\s+/g,' ');
 return '/static/products/'+(GC_PHOTOS_BY_NAME[name]||GC_PHOTOS_BY_SKU[sku]||'default-bread.jpg');
};
const iconFor=p=>{const n=p.name.toLowerCase();if(n.includes('croissant'))return '🥐';if(n.includes('loaf')||n.includes('sourdough'))return '🍞';if(n.includes('ube'))return '🍠';if(n.includes('cheese'))return '🧀';if(n.includes('strawberry'))return '🍓';if(n.includes('banana'))return '🍌';if(n.includes('cinnamon'))return '🍥';if(n.includes('roll')||n.includes('ensaymada'))return '🥮';return '🥖'};
async function req(url,opt={}){
 const resp=await fetch(url,{credentials:'same-origin',...opt,headers:{'X-Requested-With':'BreadStore',...(opt.body?{'Content-Type':'application/json'}:{}),...(opt.headers||{})}});
 let body={};try{body=await resp.json()}catch{}
 if(!resp.ok)throw new Error(body.detail||`Request failed (${resp.status}).`);
 return body;
}
let toastTimer;function toast(msg){el('#shopToast').textContent=msg;el('#shopToast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el('#shopToast').hidden=true,4000)}
function refreshAccount(){el('#accountBtn').textContent=shop.customer?shop.customer.full_name.split(' ')[0]+' ▾':'Sign in'}
async function loadProducts(){const res=await req('/api/shop/products');shop.products=res.products;renderCategories();renderProducts();renderCart()}
function renderCategories(){const categories=['All treats',...new Set(shop.products.map(p=>p.category))];el('#categoryFilters').innerHTML=categories.map(c=>`<button class="chip ${shop.category===c?'active':''}" data-action="category" data-category="${safe(c)}">${safe(c)}</button>`).join('')}
function renderProducts(){const rows=shop.products.filter(p=>(shop.category==='All treats'||p.category===shop.category)&&[p.name,p.category,p.sku].join(' ').toLowerCase().includes(shop.q));el('#productNumber').textContent=`${rows.length} fresh selections`;el('#productGrid').innerHTML=rows.map(p=>`<article class="product-card"><div class="product-picture"><img src="${productPhoto(p)}" alt="${safe(p.name)}" loading="lazy" decoding="async" onerror="this.onerror=null;this.src='/static/products/default-bread.jpg'">${p.stock<=0?'<b class="stock-label">Sold out</b>':p.stock<=10?'<b class="stock-label">Selling fast</b>':''}</div><div class="product-info"><span class="category-small">${safe(p.category)}</span><h3>${safe(p.name)}</h3><div class="product-bottom"><strong>${money(p.price)}</strong><button class="add-button" data-action="add" data-id="${p.id}" ${p.stock<1?'disabled':''}>${p.stock<1?'Unavailable':'+ Add'}</button></div></div></article>`).join('')||'<div class="empty-results">No breads match your search. Try another name.</div>'}
function cartLines(){return Object.entries(shop.cart).map(([id,quantity])=>({p:shop.products.find(p=>p.id===Number(id)),quantity})).filter(o=>o.p&&o.quantity>0)}
function renderCart(){const lines=cartLines();const total=lines.reduce((n,x)=>n+x.p.price*x.quantity,0);el('#cartCount').textContent=lines.reduce((n,x)=>n+x.quantity,0);el('#basketTotal').textContent=money(total);el('#basketItems').innerHTML=lines.length?lines.map(({p,quantity})=>`<div class="basket-row"><div class="basket-icon"><img src="${productPhoto(p)}" alt="" loading="lazy" onerror="this.onerror=null;this.src='/static/products/default-bread.jpg'"></div><div class="basket-details"><b>${safe(p.name)}</b><small>${money(p.price)} each · ${safe(p.unit)}</small><div class="basket-qty"><button data-action="minus" data-id="${p.id}" aria-label="Remove one ${safe(p.name)}">−</button><span>${quantity}</span><button data-action="plus" data-id="${p.id}" aria-label="Add one ${safe(p.name)}" ${quantity>=p.stock?'disabled':''}>+</button></div></div><b>${money(quantity*p.price)}</b></div>`).join(''):'<div class="empty-results">Your basket is waiting for something delicious. 🍞</div>';el('#placeOrderBtn').disabled=!lines.length}
function cartChange(id,delta){const p=shop.products.find(p=>p.id===id);if(!p)return;const next=(shop.cart[id]||0)+delta;if(next>p.stock){toast(`Only ${p.stock} available.`);return}if(next<=0)delete shop.cart[id];else shop.cart[id]=next;renderCart();if(delta>0)toast(`${p.name} added to basket`)}
function openBasket(){el('#overlay').hidden=false;el('#basket').classList.add('open');el('#basket').setAttribute('aria-hidden','false')}
function closeBasket(){el('#basket').classList.remove('open');el('#basket').setAttribute('aria-hidden','true');el('#overlay').hidden=true}
function modal(html){shop.modal=true;el('#modalBody').innerHTML=html;el('#modalUnderlay').hidden=false;el('#modalBody input:not([type=hidden])')?.focus()}
function closeModal(){shop.modal=null;el('#modalUnderlay').hidden=true;el('#modalBody').innerHTML=''}
function authForm(mode='login'){const login=mode==='login';modal(`<span class="section-eyebrow">YOUR BAKERY ACCOUNT</span><h2>${login?'Welcome back.':'Join our little bakery.'}</h2><p class="modal-intro">${login?'Sign in to place an order and track its progress.':'Create your free account to order fresh bread for pickup.'}</p><form id="authForm"><input type="hidden" name="mode" value="${mode}">${login?'':`<label class="form-label-text" for="fullName">Your name</label><input class="form-input" id="fullName" name="full_name" placeholder="Full name" maxlength="80" required>`}<label class="form-label-text" for="authEmail">Email address</label><input class="form-input" id="authEmail" name="email" type="email" autocomplete="email" placeholder="name@example.com" required><label class="form-label-text" for="authPassword">Password</label><input class="form-input" id="authPassword" name="password" type="password" minlength="${login?'1':'12'}" autocomplete="${login?'current-password':'new-password'}" placeholder="${login?'Your password':'At least 12 characters'}" required><p id="authError" class="modal-error" role="alert" hidden></p><button type="submit" class="full-button" style="margin-top:22px">${login?'Sign in':'Create my account'} →</button></form><button class="switch-auth" data-action="switchAuth" data-mode="${login?'register':'login'}">${login?'New here? Create an account':'Already registered? Sign in'}</button><p class="order-meta" style="margin-top:22px">Store staff? <a href="/" style="text-decoration:underline">Open admin dashboard</a></p>`);
 el('#authForm').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button[type=submit]');b.disabled=true;el('#authError').hidden=true;const f=Object.fromEntries(new FormData(e.target));const method=f.mode;delete f.mode;try{shop.customer=await req('/api/shop/'+method,{method:'POST',body:JSON.stringify(f)});refreshAccount();closeModal();toast(`Welcome, ${shop.customer.full_name.split(' ')[0]}!`);if(cartLines().length)openBasket()}catch(err){el('#authError').textContent=err.message;el('#authError').hidden=false}finally{b.disabled=false}};
}
function startCheckout(){if(!cartLines().length)return;if(!shop.customer){closeBasket();authForm('login');return}closeBasket();modal(`<span class="section-eyebrow">ALMOST THERE</span><h2>Pickup details.</h2><p class="modal-intro">Confirm the name we'll use when calling your order. No payment will be collected online.</p><div>${cartLines().map(({p,quantity})=>`<div class="order-line"><span>${quantity} × ${safe(p.name)}</span><b>${money(quantity*p.price)}</b></div>`).join('')}</div><div class="total-row" style="margin:22px 0"><b>Total to pay at pickup</b><b>${money(cartLines().reduce((a,x)=>a+x.p.price*x.quantity,0))}</b></div><form id="checkoutForm"><label class="form-label-text" for="pickupName">Pickup name</label><input id="pickupName" class="form-input" name="pickup_name" minlength="2" maxlength="80" value="${safe(shop.customer.full_name)}" required><label class="form-label-text" for="orderNote">Note to bakery (optional)</label><textarea id="orderNote" class="form-input" name="note" rows="2" maxlength="250" placeholder="Any pickup instructions?"></textarea><p id="checkoutError" class="modal-error" hidden role="alert"></p><button class="full-button" type="submit" style="margin-top:17px">Place pickup order →</button></form><p class="order-meta" style="margin-top:12px">Submitting reserves available stock. Wait for “Ready” status before pickup.</p>`);
 el('#checkoutForm').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;el('#checkoutError').hidden=true;const fd=Object.fromEntries(new FormData(e.target));try{const out=await req('/api/shop/orders',{method:'POST',body:JSON.stringify({...fd,items:cartLines().map(x=>({product_id:x.p.id,quantity:x.quantity}))})});shop.cart={};await loadProducts();modal(`<span class="section-eyebrow">ORDER RECEIVED</span><h2>Freshness incoming! ✳</h2><p class="modal-intro">Your pickup order has been sent to the bakery.</p><div class="order-card"><h3>${safe(out.order_no)}</h3><p>Status: <b>${safe(out.status)}</b></p><p>Total to pay at pickup: <b>${money(out.total)}</b></p></div><p class="modal-intro">We'll update your status as the bakery prepares your order. Check My orders to see when it's ready for pickup.</p><button data-action="myOrders" class="full-button">Track my order →</button>`)}catch(err){el('#checkoutError').textContent=err.message;el('#checkoutError').hidden=false;if(/stock|unavailable/i.test(err.message))await loadProducts()}finally{b.disabled=false}};
}
async function showOrders(){if(!shop.customer){authForm();return}try{const {orders}=await req('/api/shop/orders');modal(`<span class="section-eyebrow">SWEET MEMORIES</span><h2>My orders.</h2><p class="modal-intro">Your orders are saved to your account. Pay at the counter when you pick up.</p><div style="max-height:55vh;overflow:auto">${orders.length?orders.map(o=>`<div class="order-card"><div style="display:flex;justify-content:space-between;align-items:center"><h3>${safe(o.order_no)}</h3><span class="tag ${o.status==='Cancelled'?'cancelled':''}">${safe(o.status)}</span></div><p class="order-meta">${safe(o.created_at)} · Pickup: ${safe(o.pickup_name)}</p>${o.items.map(i=>`<div class="order-line"><span>${i.quantity} × ${safe(i.name)}</span><b>${money(i.line_total)}</b></div>`).join('')}<div class="total-row" style="margin-top:12px"><b>Total</b><b>${money(o.total)}</b></div>${o.status==='Pending'?`<button data-action="cancelOrder" data-id="${o.id}">Cancel this order</button>`:''}</div>`).join(''):'<p class="empty-results">No orders yet. Browse the menu to get started!</p>'}</div>`)}catch(err){toast(err.message)}}
async function signOut(){try{await req('/api/shop/logout',{method:'POST'})}catch{}shop.customer=null;refreshAccount();closeModal();toast('You are signed out.')}
async function init(){try{const u=await req('/api/shop/me');shop.customer=u}catch{}refreshAccount();try{await loadProducts()}catch(err){el('#productGrid').innerHTML=`<div class="empty-results">Unable to load products. ${safe(err.message)} <button data-action="retry">Try again</button></div>`}}
document.addEventListener('click',async e=>{
 const b=e.target.closest('[data-action]');if(!b)return;
 const a=b.dataset.action,id=Number(b.dataset.id);
 if(a==='category'){shop.category=b.dataset.category;renderCategories();renderProducts()}
 else if(a==='add'||a==='plus')cartChange(id,1);
 else if(a==='minus')cartChange(id,-1);
 else if(a==='closeBasket')closeBasket();
 else if(a==='closeModal')closeModal();
 else if(a==='switchAuth')authForm(b.dataset.mode);
 else if(a==='checkout')startCheckout();
 else if(a==='myOrders')await showOrders();
 else if(a==='retry')await init();
 else if(a==='cancelOrder'){if(!confirm('Cancel this pending order and release its reserved stock?'))return;try{await req(`/api/shop/orders/${id}/cancel`,{method:'POST'});await loadProducts();toast('Order cancelled.');await showOrders()}catch(err){toast(err.message)}}
 else if(a==='signOut')await signOut();
});
el('#overlay').onclick=closeBasket;
el('#modalUnderlay').addEventListener('click',e=>{if(e.target===el('#modalUnderlay'))closeModal()});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeBasket();closeModal()}});
el('#cartToggle').onclick=openBasket;
el('#ordersLink').onclick=showOrders;
el('#accountBtn').onclick=()=>shop.customer?modal(`<span class="section-eyebrow">YOUR ACCOUNT</span><h2>Hello, ${safe(shop.customer.full_name.split(' ')[0])}!</h2><p class="modal-intro">${safe(shop.customer.email)}</p><button class="full-button" data-action="myOrders">My orders →</button><button class="switch-auth" data-action="signOut">Sign out</button>`):authForm();
el('#productSearch').addEventListener('input',e=>{shop.q=e.target.value.trim().toLowerCase();renderProducts()});
init();
