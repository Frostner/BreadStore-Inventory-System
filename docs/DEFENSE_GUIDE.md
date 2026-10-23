# Project defense guide — Taglish (editable script)

The assignment's Step 22 asks you to explain the problem, goals, solution, technology, demonstration, architecture, challenges, improvements and answer questions. Use these **talking points after verifying the system yourself**. Don't memorize unsupported claims.

## 1. Introduction (1–2 minutes)

"Good day po, our project is BreadStore, a web-based Breadshop Inventory Management and Point-of-Sale System. Ang purpose po nito is mapadali ang pag-monitor ng bread products, stocks, at sales ng isang small bakery. Standalone system po ito na puwedeng i-link sa aking IT portfolio as a programming and database project."

## 2. Problem (2 minutes)

"Kapag manual ang pag-record ng stock at sales, puwedeng magkaroon ng discrepancies, duplicate records, or hindi mapansin na ubos na ang isang bread. Mahirap din makita ang best-selling products at daily revenue kapag hiwa-hiwalay ang records."

## 3. Objectives (1 minute)

"Gusto naming magkaroon ng centralized record para sa products, stocks at transactions. Included po ang CRUD, searching, validation, login, audit history, reporting at error handling."

## 4. Proposed solution (2 minutes)

"Sa BreadStore, puwede po mag-add, edit at archive ng products. Makakakita ang staff ng stock levels at alerts. Sa Point of Sale, pipili ka ng breads, ia-add sa cart, at icoconfirm ang payment. Automatic na naka-record ang sale at nababawasan ang stock sa database."

## 5. Technology (2 minutes)

"HTML, CSS at Bootstrap po ang structure and design, JavaScript ang user interactions, Python FastAPI ang backend at SQLite ang database. May SQL queries na naka-parameterize para mabawasan ang SQL injection risk. May server-side validation din kahit may browser validation na."

## 6. Live system demonstration (5–10 minutes)

**Practice this sequence:** Login → Dashboard → Inventory → Add Product → Search Product → Edit Product → Restock → Stock Activity → POS checkout → Verify reduced inventory → Reports → Logout.

Do a failing demo too: try to sell **more pieces than available**. The sale should be rejected with no partial stock deductions.

## 7. Database and architecture (3 minutes)

"May `products` table para sa item details, `sales` at `sale_items` para sa transactions, at `stock_movements` para sa audit trail. Meron ding `users` and `sessions` para sa authentication. Naka-link sila through primary and foreign keys. Ang mga presyo ay integer centavos sa database to avoid floating-point rounding problems."

## 8. Problems and solutions (2 minutes)

**Example of an engineering challenge to study, not a claim about your own debugging experience:** Concurrent checkout can cause incorrect stock if two buyers both purchase the last item. The system's solution is an SQLite transaction with `BEGIN IMMEDIATE`, which checks stock and applies all deductions atomically. Explain the exact test you ran, if asked.

## 9. Future improvements (1 minute)

"Puwede pa po mag-add ng cashier and admin roles, barcode scanner, supplier ordering, expiry alerts, at online hosting with persistent storage. Yung current stock recommendation is rule-based, not actual AI. Future improvement po ang AI forecasting kung may enough dataset at proper accuracy evaluation na."

## Possible panel questions and short answers

**Q: Where is the database?**

"Sa `data/breadstore.db`, which is an SQLite relational database file. Auto-created siya sa first run."

**Q: Is the website really connected to a database?**

"Opo. All product and sale operations go through FastAPI SQL queries and the saved records persist even after restarting the server. I can show the changed stock in Inventory and Stock Activity."

**Q: What is CRUD?**

"Create means mag-add, Read means mag-view/search, Update means mag-edit, and Delete means mag-archive ng bread. Soft delete ang ginamit para hindi mawala ang historical sales data."

**Q: What happens if inventory is insufficient?**

"Ire-reject ng API ang buong sale at walang mababawas na stock dahil transactional ang checkout."

**Q: Is this AI-assisted?**

"Hindi po actual AI model ang current version. Simple explainable rules lang para sa reorder suggestions based on current stock and recent sales. Hindi ko siya ipapakita as machine learning dahil wala pang training or evaluated prediction model."

**Q: Why SQLite instead of SQL Server/MySQL?**

"Para madali po ang local installation without configuring a separate database server. Real SQL tables and relationships pa rin ang ginamit. For bigger deployments, puwedeng i-migrate to PostgreSQL or SQL Server."

**Q: How do you protect the application?**

"Salted password hashes, authenticated sessions, HttpOnly cookies, SQL parameters, validation, and blocked cross-origin writes. Important pa rin ang HTTPS at backups kapag online na."

**Q: How can this be added to your portfolio?**

"As a separate completed project. Maglalagay ako ng project description, screenshots, GitHub link, at live demo URL kapag deployed na. Hindi ito mismo ang personal portfolio website."

**Q: How do you know the system works?**

"May automated integration tests for CRUD, auth, transaction rollback and reporting. Kailangan ko ring ipakita yung sarili kong local test results and demo."

## Student preparation checklist

Before defense, enter your own details in the README; run the system; test each feature personally; document at least one authentic problem you encountered; take your own screenshots; create your GitHub repository and explain at least one SQL query and one JavaScript-to-backend API request.


## New feature: Customer Ordering (Taglish defense Q&A)

**Q: May customer login na ba ang system?**
A: "Opo. Meron po kaming hiwalay na storefront sa `/shop` kung saan pwedeng mag-register, mag-login, mag-search ng bread, mag-add sa basket at mag-place ng pickup order. Hindi po makakapasok ang customer account sa admin inventory."

**Q: Paano nakakonekta ang admin at customer website?**
A: "Pareho po silang nakakonekta sa SQLite database. Yung products table ang source of truth para sa presyo at stock. Kapag nag-order ang customer, automatic ang reservation ng quantity sa isang SQL transaction."

**Q: Bakit hindi agad counted sa sales kapag nag-place ng order?**
A: "Pending pickup pa lang po iyon. Kapag na-pick up at nabayaran na, ika-confirm po ng admin bilang Completed, saka pa lang po madadagdag sa sales reports. Hindi na po ibabawas ulit ang stock."

**Q: Paano kung cancel ang customer?**
A: "Pending orders lang po ang pwedeng i-cancel ng customer online. Ibabalik po ng backend sa stock ang reserved quantities, at makikita po iyon sa Stock Activity. May status validation din po para hindi dalawang beses ma-cancel."

**Q: May AI ba?**
A: "Ang restock suggestions po ay rule-based computation, hindi po trained AI model. Dapat po malinaw ang distinction sa portfolio at AI usage log."
