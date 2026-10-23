/* BreadStore — vanilla JavaScript frontend. All data comes from the real SQLite API. */
'use strict';
const state = { user:null,view:'dashboard', products:[],categories:[], search:'', category:'All',status:'All',sort:'name', posFilter:'All',posSearch:'',cart:{},reportDays:30 };
const $ = sel => document.querySelector(sel);
const currency = value => new Intl.NumberFormat('en-PH',{style:'currency',currency:'PHP',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(value)||0);
const compact = n => new Intl.NumberFormat('en-PH').format(Number(n)||0);
const esc = v => String(v??'').replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const ic = (name,extra='') => `<svg class="ico ${extra}" aria-hidden="true"><use href="/static/icons.svg#${name}"/></svg>`;
const friendlyDate = (value, options={month:'short',day:'numeric',year:'numeric'}) => {try{return new Date(String(value).replace(' ','T')).toLocaleDateString('en-PH',options)}catch{return value}};
const friendlyTime = value => {try{return new Date(String(value).replace(' ','T')).toLocaleTimeString('en-PH',{hour:'numeric',minute:'2-digit'})}catch{return value}};
const productEmoji = category => ({'Everyday Bread':'🥖','Pastries':'🥐','Sweet Treats':'🧁','Loaves':'🍞','Specialty Bread':'🥨'})[category] || '🥯';
const emojiName = p => {const n=p.name.toLowerCase();if(n.includes('croissant'))return '🥐';if(n.includes('roll')||n.includes('ensaymada'))return '🥮';if(n.includes('strawberry'))return '🍓';if(n.includes('banana'))return '🍌';if(n.includes('ube'))return '🍠';if(n.includes('cinnamon'))return '🍥';if(n.includes('cheese'))return '🧀';return productEmoji(p.category)};
const emojiTone = category => ({'Pastries':'pink','Sweet Treats':'peach','Loaves':'green','Specialty Bread':'blue'})[category] || '';
const symbol = p => `<span class="product-symbol ${emojiTone(p.category)}" aria-hidden="true">${emojiName(p)}</span>`;
const statusBadge = status => `<span class="tag ${status==='In stock'?'healthy':status==='Low stock'?'low':status==='Out of stock'?'out':'archived'}">${esc(status)}</span>`;
const onlyInt = v => Number.isInteger(+v) ? +v : NaN;

async function api(path,opts={}){
 const options={credentials:'same-origin',headers:{'X-Requested-With':'BreadStore',...(opts.body?{'Content-Type':'application/json'}:{}),...(opts.headers||{})},...opts};
 const response=await fetch(path,options);
 let data={};try{data=await response.json()}catch{}
 if(!response.ok){if(response.status===401 && state.user){showLogin();}throw new Error(data.detail||`Request failed (${response.status}).`)}
 return data;
}
function toast(message,error=false){
 const root=$('#toastRoot');const el=document.createElement('div');el.className='notice-toast'+(error?' error':'');el.innerHTML=ic(error?'alert':'check')+`<span>${esc(message)}</span>`;root.append(el);setTimeout(()=>{el.remove()},4400);
}
function showLogin(){state.user=null;$('#appShell').hidden=true;$('#loginScreen').hidden=false;$('#loginPassword').value='';}
function showApp(user){state.user=user;$('#loginScreen').hidden=true;$('#appShell').hidden=false;$('#sideUser').textContent=user.email.split('@')[0];$('#todayDate').textContent=new Date().toLocaleDateString('en-PH',{weekday:'short',day:'numeric',month:'long',year:'numeric'});}
const routeNames={dashboard:'Overview',inventory:'Products & Inventory',pos:'Point of Sale',movements:'Stock Activity',reports:'Reports & Insights',orders:'Customer Orders',settings:'Settings'};
async function navigate(view){
 if(!routeNames[view])view='dashboard';
 state.view=view;$('#breadcrumbCurrent').textContent=routeNames[view];
 document.querySelectorAll('.side-link').forEach(x=>x.classList.toggle('active',x.dataset.view===view));
 $('#sidebar').classList.remove('open');if(location.hash.slice(1)!==view) history.replaceState(null,'','#'+view);
 const main=$('#mainContent');main.innerHTML='<div class="loading-screen"><div class="spinner"></div> Just a moment...</div>';
 try{
  if(view==='dashboard')await dashboard();
  if(view==='inventory')await inventory();
  if(view==='pos')await pos();
  if(view==='movements')await movements();
  if(view==='reports')await reports();
  if(view==='orders')await customerOrders();
  if(view==='settings')settings();
 }catch(e){if(!state.user)return;main.innerHTML=`<div class="card-surface card-pad"><h3>Couldn't load this page</h3><p class="muted" style="margin:12px 0 18px">${esc(e.message)}</p><button class="action-btn" id="tryAgain">Try again</button></div>`;$('#tryAgain').onclick=()=>navigate(view);}
}
function pageHead(eyebrow,title,sub,actions=''){return `<div class="page-heading"><div><div class="page-eyebrow">${esc(eyebrow)}</div><h1>${title}</h1><p>${esc(sub)}</p></div>${actions?`<div class="heading-actions">${actions}</div>`:''}</div>`}
function statCard(label,val,iconName,sub,tone=''){return `<article class="card-surface stat-card"><div class="stat-top"><span class="stat-label">${label}</span><span class="stat-icon ${tone}">${ic(iconName)}</span></div><div class="stat-val">${val}</div><div class="stat-sub">${sub}</div></article>`}
function lineChart(points){
 const arr=points.length?points:[{day:'',revenue:0}];const w=900,h=220,pl=12,pr=12,pt=17,pb=24;
 const max=Math.max(10,...arr.map(x=>+x.revenue));const top=Math.ceil(max/100)*100 || 100;
 const x=i=>pl+(arr.length===1?0:i*(w-pl-pr)/(arr.length-1));const y=v=>pt+(h-pt-pb)*(1-(+v/top));
 const pts=arr.map((p,i)=>[x(i),y(p.revenue)]);const line=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
 const fill=`${line} L${x(arr.length-1)},${h-pb} L${x(0)},${h-pb} Z`;
 const grid=[.25,.5,.75,1].map(n=>`<path d="M${pl} ${y(top*n)} H${w-pr}" stroke="#edf1eb" stroke-dasharray="4 7" fill="none"/>`).join('');
 const labels=[0,Math.floor((arr.length-1)/4),Math.floor((arr.length-1)/2),Math.floor((arr.length-1)*.75),arr.length-1].filter((v,i,a)=>a.indexOf(v)===i).map(i=>`<text x="${x(i)}" y="${h-1}" fill="#a9b1a5" font-size="12" text-anchor="middle">${friendlyDate(arr[i].day,{month:'short',day:'numeric'})}</text>`).join('');
 const pointsDots=arr.length<=14?pts.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="3.1" stroke="#fff" stroke-width="2" fill="#437552"><title>${esc(arr[i].day)} · ${currency(arr[i].revenue)}</title></circle>`).join(''):'';
 return `<svg role="img" aria-label="Sales revenue trend line chart" class="chart-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet"><defs><linearGradient id="salesGradient" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#a4c9aa" stop-opacity=".46"/><stop offset="1" stop-color="#e9f4e9" stop-opacity=".02"/></linearGradient></defs>${grid}<path d="${fill}" fill="url(#salesGradient)"/><path d="${line}" fill="none" stroke="#568365" stroke-width="3.6" stroke-linejoin="round" stroke-linecap="round"/>${pointsDots}${labels}</svg>`;
}
function noRecords(message='Nothing here yet.',icoName='🍞'){return `<div class="empty-state"><div class="empty-icon">${icoName}</div><h4>${esc(message)}</h4><p>New activity will appear here automatically.</p></div>`}

async function dashboard(){
 const d=await api('/api/overview');if(state.view!=='dashboard')return;
 const m=d.metrics;const total7=d.chart.reduce((n,x)=>n+x.revenue,0);const totalStock=m.total_products||0;
 const green=totalStock?m.healthy/totalStock*100:0, yellow=totalStock?m.low_stock/totalStock*100:0;
 const rows=d.alerts.map(p=>`<div class="alert-row"><div class="product-ident">${symbol(p)}<div><b>${esc(p.name)}</b><small>${esc(p.sku)}</small></div></div><div class="alert-stock"><strong>${p.quantity===0?'Out of stock':`${p.quantity} left`}</strong><small>Min. ${p.min_stock} ${esc(p.unit)}</small></div></div>`).join('');
 const sales=d.recent_sales.map(s=>`<div class="recent-row"><div class="product-ident"><span class="product-symbol green">🧾</span><div><div class="receipt-no">${esc(s.receipt_no)}</div><div class="receipt-meta">${friendlyDate(s.created_at,{month:'short',day:'numeric'})} · ${friendlyTime(s.created_at)} · ${esc(s.payment_method)}</div></div></div><strong>${currency(s.total)}</strong></div>`).join('');
 $('#mainContent').innerHTML=`<div class="welcome-top"><div><div class="page-eyebrow">YOUR BAKERY AT A GLANCE</div><h1>Good morning, baker! <span class="greeting-leaf">🌿</span></h1><p>Here's what's happening at your store today.</p></div><button class="action-btn" data-action="newProduct">${ic('plus')} Add new product</button></div>
 <div class="dashboard-grid">${statCard('Total products',compact(m.total_products),'box','Active bread varieties')}${statCard('Stock on hand',compact(m.units),'bag','Units across all products','blue')}${statCard('Needs attention',compact(m.low_stock+m.out_stock),'alert',`${m.out_stock} sold out · ${m.low_stock} running low`,'orange')}${statCard("Today's sales",currency(m.today_sales),'chart',`${m.today_orders} transactions today`,'green')}</div>
 <div class="dash-middle"><section class="card-surface chart-card"><div class="card-header-row"><div><h3>Sales overview</h3><p>A snapshot of the last 7 days</p></div><span class="tag healthy">Last 7 days</span></div><div class="total-revenue">${currency(total7)} <small>in revenue</small></div><div class="chart-wrap" style="margin-top:12px">${lineChart(d.chart)}</div></section>
 <section class="card-surface health-card"><div class="card-header-row"><div><h3>Inventory health</h3><p>Current stock status</p></div>${ic('activity')}</div><div class="health-visual"><div class="donut" style="background:conic-gradient(#6f9b75 0% ${green}%,#e3b372 ${green}% ${green+yellow}%,#d87969 ${green+yellow}% 100%)"><div class="donut-text"><strong>${totalStock}</strong><span>products</span></div></div><div class="health-legend"><div class="legend-row"><span class="legend-dot" style="background:#6f9b75"></span>Healthy <b>${m.healthy}</b></div><div class="legend-row"><span class="legend-dot" style="background:#e3b372"></span>Low stock <b>${m.low_stock}</b></div><div class="legend-row"><span class="legend-dot" style="background:#d87969"></span>Sold out <b>${m.out_stock}</b></div></div></div></section></div>
 <div class="dash-bottom"><section class="card-surface card-pad"><div class="card-header-row"><div><h3>Needs a refill <span class="pill-count">${m.low_stock+m.out_stock}</span></h3><p>Products that may need restocking</p></div><button class="text-link" data-view="inventory">View all ${ic('arrow-right')}</button></div>${rows||noRecords('Every shelf is looking good!','✨')}</section>
 <section class="card-surface card-pad"><div class="card-header-row"><div><h3>Recent transactions</h3><p>The latest sales in your bakery</p></div><button class="text-link" data-view="reports">View reports ${ic('arrow-right')}</button></div>${sales||noRecords('No sales just yet.','🧾')}</section></div>
 <div class="bread-banner"><div><span>FRESH IDEAS, BETTER DECISIONS</span><h3>Keep your shelves full of favorites.</h3><p>See what customers love and which products need a refill.</p></div><button class="action-btn" data-view="reports">Explore insights ${ic('arrow-right')}</button></div>`;
}
function inventoryRows(){
 const arr=state.products;
 const html=arr.map(p=>`<tr><td class="td-product"><div class="product-ident">${symbol(p)}<div><b>${esc(p.name)}</b><small>${esc(p.sku)}</small></div></div></td><td>${esc(p.category)}</td><td><b>${currency(p.price)}</b></td><td>${currency(p.cost)}</td><td><span class="stock-number ${p.quantity===0?'out-val':p.quantity<=p.min_stock?'low-val':''}">${compact(p.quantity)}</span> <span class="muted">${esc(p.unit)}</span></td><td>${statusBadge(p.status)}</td><td class="right"><div class="row-actions">${p.archived?`<button class="icon-btn" title="Restore product" data-action="restore" data-id="${p.id}">${ic('restore')}</button>`:`<button class="icon-btn" title="Adjust stock" data-action="adjust" data-id="${p.id}">${ic('plus')}</button><button class="icon-btn" title="Edit product" data-action="edit" data-id="${p.id}">${ic('edit')}</button><button class="icon-btn danger" title="Archive product" data-action="delete" data-id="${p.id}">${ic('trash')}</button>`}</div></td></tr>`).join('');
 return `<div class="table-scroll"><table class="data-table"><thead><tr><th>PRODUCT</th><th>CATEGORY</th><th>SELLING PRICE</th><th>COST</th><th>STOCK</th><th>STATUS</th><th class="right">ACTIONS</th></tr></thead><tbody>${html||`<tr><td colspan="7">${noRecords('No matching products found.','🔎')}</td></tr>`}</tbody></table></div><div class="inventory-meta"><span>Showing ${arr.length} ${arr.length===1?'product':'products'}</span><span>Stock changes are recorded for audit history</span></div>`;
}
async function fetchInventoryRows(preserve=false){
 const qs=new URLSearchParams({q:state.search,category:state.category,status:state.status,sort:state.sort});const result=await api('/api/products?'+qs.toString());if(state.view!=='inventory')return;
 state.products=result.products;state.categories=result.categories;
 if(preserve){const target=$('#productResults');if(target)target.innerHTML=inventoryRows();if($('#shownCount'))$('#shownCount').textContent=result.products.length;}
 else {renderInventory()}
}
async function inventory(){await fetchInventoryRows()}
function renderInventory(){
 $('#mainContent').innerHTML=pageHead('KEEP IT FRESH','Products & Inventory','Manage your bread catalog, track stock, and update pricing.',`<button class="action-btn ghost" data-action="downloadProducts">${ic('download')} Export CSV</button><button class="action-btn" data-action="newProduct">${ic('plus')} Add product</button>`)+`
 <div class="toolbar"><label class="searchbox">${ic('search')}<input id="inventorySearch" placeholder="Search bread, SKU, category..." value="${esc(state.search)}" autocomplete="off" aria-label="Search inventory"></label>
 <select id="inventoryCategory" class="filter-select" aria-label="Filter by category"><option value="All">All categories</option>${state.categories.map(c=>`<option value="${esc(c)}" ${state.category===c?'selected':''}>${esc(c)}</option>`).join('')}</select>
 <select id="inventoryStatus" class="filter-select" aria-label="Filter by stock status">${['All','In stock','Low stock','Out of stock','Archived'].map(s=>`<option value="${s}" ${s===state.status?'selected':''}>${s==='All'?'All stock':s}</option>`).join('')}</select>
 <select id="inventorySort" class="filter-select" aria-label="Sort inventory"><option value="name" ${state.sort==='name'?'selected':''}>Name A–Z</option><option value="stock" ${state.sort==='stock'?'selected':''}>Lowest stock</option><option value="price" ${state.sort==='price'?'selected':''}>Highest price</option><option value="newest" ${state.sort==='newest'?'selected':''}>Recently added</option></select></div>
 <section class="card-surface table-card"><div class="table-head"><h3>All products <span id="shownCount" class="pill-count">${state.products.length}</span></h3><small>Actions · Edit / Restock / Archive</small></div><div id="productResults">${inventoryRows()}</div></section>`;
 let t;
 $('#inventorySearch').addEventListener('input', e=>{state.search=e.target.value;clearTimeout(t);t=setTimeout(()=>fetchInventoryRows(true).catch(x=>toast(x.message,true)),280)});
 $('#inventoryCategory').onchange=e=>{state.category=e.target.value;fetchInventoryRows(true).catch(x=>toast(x.message,true))};
 $('#inventoryStatus').onchange=e=>{state.status=e.target.value;fetchInventoryRows(true).catch(x=>toast(x.message,true))};
 $('#inventorySort').onchange=e=>{state.sort=e.target.value;fetchInventoryRows(true).catch(x=>toast(x.message,true))};
}
function openModal(title,subtitle,body,footer=''){
 $('#modalRoot').innerHTML=`<div class="modal-backdrop-custom" id="modalOverlay"><section class="modal-box" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="modal-top"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div><button class="icon-btn" data-action="closeModal" aria-label="Close dialog">${ic('close')}</button></div>${body}${footer}</section></div>`;
 $('#modalOverlay').addEventListener('click',e=>{if(e.target.id==='modalOverlay')closeModal()});
 const focus=$('#modalRoot input, #modalRoot select');if(focus)focus.focus();
}
function closeModal(){$('#modalRoot').innerHTML=''}
function productModal(id=null){
 const p=id?state.products.find(x=>x.id===id):null;
 const title=p?'Edit bread product':'Add a bread product';
 const catNames=[...new Set([...state.categories,'Everyday Bread','Pastries','Sweet Treats','Loaves','Specialty Bread'])];
 const body=`<form id="productForm"><div class="modal-body"><div class="form-grid">
 <div class="form-control-wrap"><label>Product SKU</label><input required maxlength="30" minlength="2" name="sku" class="field" placeholder="BRD-014" value="${esc(p?.sku||'')}"></div>
 <div class="form-control-wrap"><label>Unit</label><select name="unit" class="field">${['pcs','loaf','pack','box'].map(x=>`<option value="${x}" ${p?.unit===x?'selected':''}>${x}</option>`).join('')}</select></div>
 <div class="form-control-wrap wide"><label>Bread / product name</label><input required maxlength="80" minlength="2" name="name" class="field" placeholder="e.g. Classic Pandesal" value="${esc(p?.name||'')}"></div>
 <div class="form-control-wrap wide"><label>Category</label><select name="category" class="field">${catNames.map(x=>`<option value="${esc(x)}" ${(p?.category||'Everyday Bread')===x?'selected':''}>${esc(x)}</option>`).join('')}</select></div>
 <div class="form-control-wrap"><label>Selling price (₱)</label><input required min="0.01" max="1000000" step="0.01" type="number" name="price" class="field" placeholder="18.00" value="${p?.price??''}"></div>
 <div class="form-control-wrap"><label>Cost per unit (₱)</label><input required min="0" max="1000000" step="0.01" type="number" name="cost" class="field" placeholder="9.00" value="${p?.cost??''}"></div>
 ${p?'':`<div class="form-control-wrap"><label>Opening stock</label><input required min="0" max="1000000" type="number" name="quantity" class="field" value="0"></div>`}
 <div class="form-control-wrap ${p?'wide':''}"><label>Low-stock alert at</label><input required min="0" max="1000000" type="number" name="min_stock" class="field" value="${p?.min_stock??10}"></div>
 </div>${p?'<p class="small-description">To maintain a reliable audit trail, adjust stock separately instead of editing it here.</p>':''}</div>
 <div class="modal-footer-row"><button type="button" class="action-btn ghost" data-action="closeModal">Cancel</button><button type="submit" class="action-btn">${ic('check')} ${p?'Save changes':'Create product'}</button></div></form>`;
 openModal(title,p?'Update product information':'Add something delicious to your shelves',body);
 $('#productForm').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);const data=Object.fromEntries(fd.entries());for(const k of ['price','cost','min_stock','quantity'])if(k in data)data[k]=Number(data[k]);if(!data.name.trim()||!data.sku.trim())return toast('Please complete all required fields.',true);
  const btn=e.target.querySelector('[type=submit]');btn.disabled=true;try{await api(p?`/api/products/${p.id}`:'/api/products',{method:p?'PUT':'POST',body:JSON.stringify(data)});closeModal();toast(p?'Product updated successfully.':'Bread added to your inventory.');await navigate(state.view);}catch(err){toast(err.message,true)}finally{btn.disabled=false}
 };
}
function adjustModal(id){const p=state.products.find(x=>x.id===id);if(!p)return;
 openModal('Adjust stock',`Keep a record of every stock movement for ${p.name}`,`<form id="adjustForm"><div class="modal-body"><div class="stock-big-number"><b>${p.quantity}</b> ${esc(p.unit)} currently in stock</div><div class="form-grid"><div class="form-control-wrap wide"><label>Adjustment (+ to add, − to remove)</label><input class="field" name="change" type="number" required min="-1000000" max="1000000" placeholder="e.g. 30 or -5"><p class="field-note">Examples: 25 to restock, -2 for damaged bread.</p></div><div class="form-control-wrap wide"><label>Reason</label><select class="field" name="reason"><option>Restock</option><option>Damage / waste</option><option>Inventory correction</option></select></div><div class="form-control-wrap wide"><label>Note (optional)</label><input name="note" class="field" maxlength="200" placeholder="e.g. Morning bakery delivery"></div></div></div><div class="modal-footer-row"><button type="button" class="action-btn ghost" data-action="closeModal">Cancel</button><button type="submit" class="action-btn">Save stock change</button></div></form>`);
 $('#adjustForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);const change=Number(f.get('change'));if(!Number.isInteger(change)||!change)return toast('Enter a non-zero whole number.',true);const btn=e.target.querySelector('[type=submit]');btn.disabled=true;try{await api(`/api/products/${p.id}/adjust`,{method:'POST',body:JSON.stringify({change,reason:f.get('reason'),note:f.get('note')})});closeModal();toast('Stock adjusted and recorded in activity history.');await navigate(state.view);}catch(err){toast(err.message,true)}finally{btn.disabled=false}};
}
async function archiveProduct(id){const p=state.products.find(x=>x.id===id);if(!p)return;if(!confirm(`Archive "${p.name}"? It will disappear from active products, but past sales and stock records will remain intact.`))return;try{await api(`/api/products/${id}`,{method:'DELETE'});toast('Product archived.');await fetchInventoryRows()}catch(e){toast(e.message,true)}}
async function restoreProduct(id){try{await api(`/api/products/${id}/restore`,{method:'POST'});toast('Product restored.');await fetchInventoryRows()}catch(e){toast(e.message,true)}}

async function pos(){const [result,sales]=await Promise.all([api('/api/products'),api('/api/sales?limit=6')]);if(state.view!=='pos')return;state.products=result.products;state.categories=result.categories;state.recentSales=sales.sales;renderPOS()}
function posCard(p){const out=p.quantity===0;return `<button class="pos-card" ${out?'disabled':''} data-action="addCart" data-id="${p.id}"><div class="pos-image ${emojiTone(p.category)}">${emojiName(p)}</div><h4>${esc(p.name)}</h4><p>${out?'Sold out':`${p.quantity} ${esc(p.unit)} available`}</p><div class="pos-price"><strong>${currency(p.price)}</strong><span class="pos-add">+</span></div></button>`}
function posCart(){const lines=Object.values(state.cart),subtotal=lines.reduce((a,x)=>a+x.price*x.qty,0);return `<div class="pos-cart-head"><h3>Current order <span class="pill-count">${lines.reduce((a,x)=>a+x.qty,0)}</span></h3><button class="text-link" data-action="clearCart" ${lines.length?'':'disabled'}>Clear all</button></div><div>${lines.length?lines.map(p=>`<div class="cart-line">${symbol(p)}<div class="cart-line-info"><b>${esc(p.name)}</b><small>${currency(p.price)} each</small></div><div class="cart-line-right"><strong>${currency(p.price*p.qty)}</strong><div class="qty-control"><button data-action="changeCart" data-id="${p.id}" data-delta="-1" aria-label="Decrease ${esc(p.name)}">−</button><span>${p.qty}</span><button data-action="changeCart" data-id="${p.id}" data-delta="1" aria-label="Increase ${esc(p.name)}">+</button></div></div></div>`).join(''):`<div class="cart-empty"><span>🧺</span><b>Your basket is empty</b><p>Add a product from the menu to start a new sale.</p></div>`}</div><div class="cart-footer"><div class="cart-subtotal"><span>Subtotal</span><b>${currency(subtotal)}</b></div><div class="cart-subtotal"><span>Additional fees</span><b>₱0.00</b></div><div class="cart-total"><span>Total</span><strong>${currency(subtotal)}</strong></div><button ${lines.length?'':'disabled'} data-action="checkout" class="action-btn cart-pay">Proceed to payment ${ic('arrow-right')}</button></div>`}
function renderPOS(){
 const filtered=state.products.filter(p=>(state.posFilter==='All'||p.category===state.posFilter)&&(!state.posSearch||p.name.toLowerCase().includes(state.posSearch.toLowerCase())||p.sku.toLowerCase().includes(state.posSearch.toLowerCase())));
 const selectedSearch=$('#posSearch')===document.activeElement;
 $('#mainContent').innerHTML=pageHead('FROM OVEN TO COUNTER','Point of Sale','Record each sale and update your inventory automatically.',`<button class="action-btn ghost" data-action="downloadSales">${ic('download')} Sales CSV</button>`)+`
 <div class="pos-layout"><div class="pos-products"><div class="sale-search"><label class="searchbox">${ic('search')}<input id="posSearch" placeholder="Find a delicious bread..." value="${esc(state.posSearch)}" aria-label="Search products for sale"></label></div><div class="pos-filter">${['All',...state.categories].map(c=>`<button class="chip-btn ${c===state.posFilter?'active':''}" data-action="posCategory" data-category="${esc(c)}">${c==='All'?'All items':esc(c)}</button>`).join('')}</div><div id="posGrid" class="pos-grid">${filtered.length?filtered.map(posCard).join(''):noRecords('No products found.','🔎')}</div></div><aside id="cartPanel" class="card-surface pos-cart">${posCart()}</aside></div>
 <section class="card-surface table-card" style="margin-top:20px"><div class="table-head"><h3>Latest completed sales</h3><small>These transactions are saved in your database</small></div>${saleHistoryTable(state.recentSales||[])}</section>`;
 $('#posSearch').addEventListener('input',e=>{state.posSearch=e.target.value;const p=state.products.filter(x=>(state.posFilter==='All'||x.category===state.posFilter)&&(!state.posSearch||x.name.toLowerCase().includes(state.posSearch.toLowerCase())||x.sku.toLowerCase().includes(state.posSearch.toLowerCase())));$('#posGrid').innerHTML=p.length?p.map(posCard).join(''):noRecords('No products found.','🔎')});
}
function addCart(id){const p=state.products.find(x=>x.id===id);if(!p||p.quantity===0)return toast('This product is out of stock.',true);const inCart=state.cart[id]||{...p,qty:0};if(inCart.qty>=p.quantity)return toast('Not enough stock to add more.',true);inCart.qty+=1;state.cart[id]=inCart;$('#cartPanel').innerHTML=posCart();}
function changeCart(id,delta){const p=state.cart[id];if(!p)return;const next=p.qty+delta;if(next<=0)delete state.cart[id];else if(next>p.quantity)return toast('That exceeds the available stock.',true);else p.qty=next;$('#cartPanel').innerHTML=posCart()}
function checkoutModal(){const lines=Object.values(state.cart);if(!lines.length)return;const total=lines.reduce((n,l)=>n+l.price*l.qty,0);
 openModal('Complete this sale','Confirm payment and update stock automatically',`<form id="checkoutForm"><div class="modal-body"><div class="stock-big-number"><b>${currency(total)}</b> to collect</div><div class="form-control-wrap"><label>Payment method</label><select name="payment_method" class="field"><option>Cash</option><option>GCash</option><option>Card</option></select></div><div class="small-description">${lines.reduce((a,x)=>a+x.qty,0)} items from ${lines.length} different products. Once confirmed, this transaction is permanently saved and inventory is deducted.</div></div><div class="modal-footer-row"><button type="button" class="action-btn ghost" data-action="closeModal">Back</button><button type="submit" class="action-btn">${ic('check')} Confirm sale</button></div></form>`);
 $('#checkoutForm').onsubmit=async e=>{e.preventDefault();const submit=e.target.querySelector('[type=submit]');submit.disabled=true;try{const result=await api('/api/sales',{method:'POST',body:JSON.stringify({items:lines.map(p=>({product_id:p.id,quantity:p.qty})),payment_method:new FormData(e.target).get('payment_method')})});state.cart={};state.posSearch='';closeModal();toast(`Sale completed! Receipt ${result.receipt_no} · ${currency(result.total)}`);await navigate('pos');}catch(err){toast(err.message,true)}finally{submit.disabled=false}}
}
function saleHistoryTable(arr){return arr.length?`<div class="table-scroll"><table class="data-table"><thead><tr><th>RECEIPT NO.</th><th>DATE</th><th>ITEMS</th><th>PAYMENT</th><th class="right">TOTAL</th></tr></thead><tbody>${arr.map(s=>`<tr><td><b class="mono">${esc(s.receipt_no)}</b></td><td>${friendlyDate(s.created_at)} · ${friendlyTime(s.created_at)}</td><td><span title="${esc(s.description)}">${esc(s.units)} units</span></td><td>${esc(s.payment_method)}</td><td class="right"><b>${currency(s.total)}</b></td></tr>`).join('')}</tbody></table></div>`:noRecords('No completed sales yet.','🧾')}

async function movements(){const d=await api('/api/stock-movements?limit=200');if(state.view!=='movements')return;
 $('#mainContent').innerHTML=pageHead('TRACE EVERY CHANGE','Stock Activity','A reliable record of sales, restocks, and inventory adjustments.')+`<section class="card-surface table-card"><div class="table-head"><h3>Stock movement history <span class="pill-count">${d.movements.length}</span></h3><small>Newest activity first</small></div><div class="table-scroll"><table class="data-table"><thead><tr><th>DATE & TIME</th><th>PRODUCT</th><th>MOVEMENT</th><th>REASON</th><th>NOTE / RECEIPT</th><th>RECORDED BY</th></tr></thead><tbody>${d.movements.map(m=>`<tr><td>${friendlyDate(m.created_at)}<br/><span class="muted">${friendlyTime(m.created_at)}</span></td><td><b>${esc(m.product_name)}</b><br/><span class="muted">${esc(m.sku)}</span></td><td><b style="color:${m.change_amount>0?'#4c9865':'#ca7e55'}">${m.change_amount>0?'+':''}${compact(m.change_amount)}</b></td><td>${esc(m.reason)}</td><td>${esc(m.note)||'—'}</td><td>${esc(m.actor.split('@')[0])}</td></tr>`).join('')||`<tr><td colspan="6">${noRecords()}</td></tr>`}</tbody></table></div><div class="inventory-meta"><span>Showing up to 200 recent movements</span><span>All quantities are recorded in the database</span></div></section>`;
}
async function reports(){const [data,insights,allSales]=await Promise.all([api('/api/reports?days='+state.reportDays),api('/api/insights'),api('/api/sales?limit=20')]);if(state.view!=='reports')return;
 const tops=data.top_products;const max=Math.max(1,...tops.map(x=>x.units));const topHtml=tops.map((p,i)=>`<div class="top-product-row"><span class="rank">0${i+1}</span><div><b>${esc(p.name)}</b><div class="mini-bar"><div class="mini-bar-fill" style="width:${p.units/max*100}%"></div></div></div><strong>${p.units}</strong></div>`).join('');
 const recs=insights.recommendations.map(p=>`<div class="card-surface insight-card">${symbol(p)}<div class="insight-body"><b>${esc(p.name)}</b><p>${p.quantity} in stock · ${p.sold14} sold in 14 days</p></div><div class="insight-order"><b>+${p.recommended_order}</b><small>suggested units</small></div></div>`).join('');
 $('#mainContent').innerHTML=pageHead('SEE THE BIGGER PICTURE','Reports & Insights','Make confident decisions based on your actual sales data.',`<select id="daysSelect" class="filter-select" aria-label="Report period">${[7,30,90].map(n=>`<option value="${n}" ${n===state.reportDays?'selected':''}>Last ${n} days</option>`).join('')}</select><button class="action-btn ghost" data-action="downloadSales">${ic('download')} Export sales</button>`)+`
 <div class="report-kpis">${statCard('Total revenue',currency(data.revenue),'chart',`Last ${data.days} days`)}${statCard('Orders completed',compact(data.orders),'receipt','Recorded transactions','blue')}${statCard('Units sold',compact(data.units_sold),'bag','Across all bread types','orange')}${statCard('Estimated gross profit',currency(data.profit),'activity','Revenue minus recorded product costs','green')}</div>
 <div class="card-surface chart-card"><div class="card-header-row"><div><h3>Revenue over time</h3><p>Daily sales performance over ${data.days} days</p></div><span class="tag healthy">${data.days}-day report</span></div><div class="chart-wrap">${lineChart(data.chart)}</div></div>
 <div class="report-flex"><section class="card-surface card-pad"><div class="card-header-row"><div><h3>Best-selling breads</h3><p>Ranked by units sold in the selected period</p></div></div>${topHtml||noRecords('No sales for this period.')}</section><section class="card-surface card-pad"><div class="card-header-row"><div><h3>Sales by category</h3><p>Revenue across your product groups</p></div></div>${data.categories.map(c=>`<div class="category-row"><span>${esc(c.category)}</span><strong>${currency(c.revenue)}</strong></div>`).join('')||noRecords('No category sales yet.')}</section></div>
 <div class="recommendation-header"><div><h3>✳ Smart restock suggestions</h3><p>Based on stock levels and recent selling speed</p></div><span class="tag healthy">Rule-based</span></div><div class="insight-list">${recs||`<div class="card-surface card-pad">${noRecords('No restocks needed at the moment!','✨')}</div>`}</div><p class="method-note"><b>How recommendations work:</b> ${esc(insights.method)}</p>
 <section class="card-surface table-card" style="margin-top:24px"><div class="table-head"><h3>Sales history</h3><small>The 20 most recent transactions</small></div>${saleHistoryTable(allSales.sales)}</section>`;
 $('#daysSelect').onchange=e=>{state.reportDays=Number(e.target.value);reports().catch(x=>toast(x.message,true))};
}
/* Admin-only customer pickup orders. Product stock is reserved by customer checkout,
   and an actual POS sale is recorded after the admin completes the pickup. */
let ordersState={status:'All',search:''};
async function customerOrders(){
 const qs=new URLSearchParams({status:ordersState.status,q:ordersState.search});
 const data=await api('/api/customer-orders?'+qs.toString());
 if(state.view!=='orders')return;
 const next={Pending:['Preparing','Cancelled'],Preparing:['Ready','Cancelled'],Ready:['Completed','Cancelled'],Completed:[],Cancelled:[]};
 $('#mainContent').innerHTML=pageHead('ONLINE PICKUP ORDERS','Customer Orders','Review incoming bakery orders, prepare them, and mark pickups as completed.',`<a href="/shop" target="_blank" rel="noopener" class="action-btn ghost">${ic('bag')} Open customer store ↗</a>`)+`
 <div class="orders-toolbar"><div><label class="orders-label" for="orderSearch">Search orders</label><input id="orderSearch" class="field" type="search" placeholder="Order number or customer" value="${esc(ordersState.search)}" maxlength="100"></div><div><label class="orders-label" for="orderStatus">Status</label><select id="orderStatus" class="filter-select">${['All','Pending','Preparing','Ready','Completed','Cancelled'].map(s=>`<option value="${s}" ${s===ordersState.status?'selected':''}>${s}</option>`).join('')}</select></div></div>
 <div class="orders-list">${data.orders.length?data.orders.map(o=>`<article class="card-surface order-admin-card"><div class="order-admin-header"><div><h3>${esc(o.order_no)}</h3><p>${esc(o.customer_name)} · ${esc(o.customer_email)}</p><small>${esc(o.created_at)}</small></div><span class="order-status status-${o.status.toLowerCase()}">${esc(o.status)}</span></div><div class="order-admin-body"><div class="order-items">${o.items.map(it=>`<div class="order-item"><span>${it.quantity} × ${esc(it.name)}</span><strong>${currency(it.line_total)}</strong></div>`).join('')}</div><div class="order-admin-meta"><span>Pickup name: <b>${esc(o.pickup_name)}</b></span>${o.note?`<span>Customer note: ${esc(o.note)}</span>`:''}<span>Payment: <b>At pickup (not collected online)</b></span><strong>Order total: ${currency(o.total)}</strong></div></div>${next[o.status].length?`<div class="order-admin-actions">${next[o.status].map(newStatus=>`<button class="action-btn ${newStatus==='Cancelled'?'ghost':''}" data-action="orderStatus" data-id="${o.id}" data-status="${newStatus}">${newStatus==='Cancelled'?'Cancel order':newStatus==='Preparing'?'Start preparing':newStatus==='Ready'?'Mark ready for pickup':'Complete pickup & record sale'}</button>`).join('')}</div>`:''}</article>`).join(''):noRecords('No matching pickup orders.','🥐')}</div>
 <p class="method-note">Stock is reserved immediately when the customer submits an order. Cancelling releases the reserved stock. Completing an order records one sale, without deducting stock a second time. All pickup payments happen in person.</p>`;
 $('#orderStatus').onchange=e=>{ordersState.status=e.target.value;customerOrders().catch(x=>toast(x.message,true))};
 $('#orderSearch').onchange=e=>{ordersState.search=e.target.value.trim();customerOrders().catch(x=>toast(x.message,true))};
 $('#orderSearch').addEventListener('keydown',e=>{if(e.key==='Enter'){ordersState.search=e.target.value.trim();customerOrders().catch(x=>toast(x.message,true))}});
}
async function updateCustomerOrder(id,newStatus){
 const statement=newStatus==='Completed'?'Confirm this order was picked up and paid for? This records a sale.':newStatus==='Cancelled'?'Cancel this order and return reserved stock to inventory?':`Change order status to ${newStatus}?`;
 if(!confirm(statement))return;
 try{await api('/api/customer-orders/'+id,{method:'PATCH',body:JSON.stringify({status:newStatus})});toast('Order marked '+newStatus+'.');await customerOrders()}catch(err){toast(err.message,true)}
}
function settings(){
 $('#mainContent').innerHTML=pageHead('KEEP THINGS SECURE','Account & Settings','Manage your administrator access and see how your system works.')+`<div class="settings-layout"><section class="card-surface card-pad"><div class="card-header-row"><div><h3>Account information</h3><p>Your secure bakery administrator profile</p></div>${ic('user')}</div><div class="profile-line"><div class="avatar">A</div><div><b>Bakery administrator</b><span>${esc(state.user.email)}</span></div></div><div class="keyline"></div><div class="detail-row"><span>Role</span><strong>Administrator</strong></div><div class="detail-row"><span>Database</span><strong>SQLite · Persistent</strong></div><div class="detail-row"><span>Session</span><strong>Secure HttpOnly cookie</strong></div><div class="keyline"></div><h4 class="settings-subhead">Change your password</h4><form class="settings-form" id="passwordForm"><label>Current password</label><input class="field" type="password" name="current_password" autocomplete="current-password" required><label>New password (12+ characters)</label><input class="field" type="password" name="new_password" minlength="12" autocomplete="new-password" required><button type="submit" class="action-btn">${ic('shield')} Update password</button></form></section><section class="card-surface card-pad"><div class="card-header-row"><div><h3>Made to keep your bakery moving</h3><p>What's running behind the scenes</p></div>${ic('sparkle')}</div><div class="tech-list">${['Python + FastAPI backend','SQLite relational database (SQL)','HTML, CSS, JavaScript & Bootstrap','CRUD with input validation','Protected admin authentication','Transactional inventory deduction','Stock activity and reporting','CSV exports & rule-based recommendations'].map(t=>`<div class="tech-row">${ic('check')}<span>${esc(t)}</span></div>`).join('')}</div><div class="keyline"></div><p class="small-description">This system is a standalone project that you can link to from your BSIT portfolio. It is not your portfolio website.</p><div style="margin-top:22px"><button class="action-btn ghost" data-action="logout">${ic('logout')} Sign out</button></div></section></div>`;
 $('#passwordForm').onsubmit=async e=>{e.preventDefault();const form=e.target,button=form.querySelector('button');button.disabled=true;try{await api('/api/auth/change-password',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form).entries()))});form.reset();toast('Password updated successfully.');}catch(err){toast(err.message,true)}finally{button.disabled=false}};
}
async function signOut(){try{await api('/api/auth/logout',{method:'POST'});}catch{}showLogin();}
function download(kind){location.href='/api/export/'+kind}

document.addEventListener('click',async e=>{
 const nav=e.target.closest('[data-view]');if(nav){e.preventDefault();if(state.user)navigate(nav.dataset.view);return}
 const b=e.target.closest('[data-action]');if(!b)return;const act=b.dataset.action,id=Number(b.dataset.id);
 if(act==='closeModal')closeModal();
 if(act==='newProduct')productModal();
 if(act==='edit')productModal(id);
 if(act==='adjust')adjustModal(id);
 if(act==='delete')await archiveProduct(id);
 if(act==='restore')await restoreProduct(id);
 if(act==='downloadProducts')download('products');
 if(act==='downloadSales')download('sales');
 if(act==='addCart')addCart(id);
 if(act==='changeCart')changeCart(id,Number(b.dataset.delta));
 if(act==='clearCart'){state.cart={};$('#cartPanel').innerHTML=posCart()}
 if(act==='posCategory'){state.posFilter=b.dataset.category;renderPOS()}
 if(act==='checkout')checkoutModal();
 if(act==='logout')await signOut();
 if(act==='orderStatus')await updateCustomerOrder(id,b.dataset.status);
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
$('#loginForm').addEventListener('submit',async e=>{
 e.preventDefault();$('#loginError').hidden=true;const button=$('#loginButton');button.disabled=true;button.firstChild.textContent='Signing in... ';
 try{const u=await api('/api/auth/login',{method:'POST',body:JSON.stringify({email:$('#loginEmail').value,password:$('#loginPassword').value})});showApp(u);await navigate(location.hash.slice(1)||'dashboard');}
 catch(err){$('#loginError').textContent=err.message;$('#loginError').hidden=false;}
 finally{button.disabled=false;button.firstChild.textContent='Sign in to dashboard '}
});
$('#showPassword').onclick=()=>{const fld=$('#loginPassword');fld.type=fld.type==='password'?'text':'password';$('#showPassword').textContent=fld.type==='password'?'Show':'Hide'};
$('#logoutBtn').onclick=signOut;
$('#menuToggle').onclick=()=>$('#sidebar').classList.toggle('open');
window.addEventListener('hashchange',()=>{const v=location.hash.slice(1);if(state.user&&routeNames[v]&&v!==state.view)navigate(v)});
(async()=>{try{const u=await api('/api/auth/me');showApp(u);await navigate(location.hash.slice(1)||'dashboard')}catch{showLogin()}})();
