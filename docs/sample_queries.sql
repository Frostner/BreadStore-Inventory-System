-- BreadStore example SQL for your BSIT portfolio defense.
-- Run on a COPY of breadstore.db, or use a read-only SQLite viewer.

-- 1. Bread with low stock
SELECT sku, name, category, quantity, min_stock
FROM products
WHERE archived = 0 AND quantity <= min_stock
ORDER BY quantity ASC;

-- 2. Count and value of products currently active
SELECT COUNT(*) AS unique_products,
       SUM(quantity) AS pieces_in_stock,
       ROUND(SUM(quantity * cost_cents) / 100.0, 2) AS stock_cost_value_php
FROM products
WHERE archived = 0;

-- 3. Sales totals by date
SELECT DATE(created_at) AS sale_date,
       COUNT(*) AS number_of_orders,
       ROUND(SUM(total_cents) / 100.0, 2) AS revenue_php
FROM sales
GROUP BY DATE(created_at)
ORDER BY sale_date DESC;

-- 4. Best-selling bread using JOIN, GROUP BY and ORDER BY
SELECT si.product_name AS bread,
       SUM(si.quantity) AS pieces_sold,
       ROUND(SUM(si.line_total_cents) / 100.0, 2) AS revenue_php
FROM sale_items si
JOIN sales s ON s.id = si.sale_id
GROUP BY si.product_id
ORDER BY pieces_sold DESC
LIMIT 10;

-- 5. Inventory changes and staff member (LEFT JOIN preserves demo events)
SELECT m.created_at, p.name, m.change_amount, m.reason,
       COALESCE(u.email, 'Demo data') AS recorded_by
FROM stock_movements m
JOIN products p ON p.id = m.product_id
LEFT JOIN users u ON u.id = m.actor_id
ORDER BY m.created_at DESC, m.id DESC
LIMIT 30;
