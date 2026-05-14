-- E-commerce sample data for saas-graph testing
-- 50 products, 200 customers, 500 orders, ~1500 order items

BEGIN;

-- ============================================================
-- Tables
-- ============================================================

CREATE TABLE products (
    product_id   SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    sku          TEXT UNIQUE NOT NULL,
    category     TEXT NOT NULL,
    price        NUMERIC(10,2) NOT NULL,
    cost         NUMERIC(10,2) NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE customers (
    customer_id    SERIAL PRIMARY KEY,
    name           TEXT NOT NULL,
    email          TEXT UNIQUE NOT NULL,
    signup_date    DATE NOT NULL,
    lifetime_value NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date    TIMESTAMP NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('pending','shipped','delivered','returned','cancelled')),
    total_amount  NUMERIC(10,2) NOT NULL DEFAULT 0,
    shipping_cost NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE order_items (
    item_id    SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity   INTEGER NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL,
    line_total NUMERIC(10,2) NOT NULL
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);

-- ============================================================
-- Products  (50 rows)
-- ============================================================

INSERT INTO products (name, sku, category, price, cost, stock_quantity, is_active) VALUES
('Wireless Bluetooth Headphones',   'ELEC-001', 'Electronics',    79.99,  35.00, 142, TRUE),
('USB-C Charging Cable 6ft',        'ELEC-002', 'Electronics',    12.99,   4.50,  530, TRUE),
('Mechanical Keyboard RGB',         'ELEC-003', 'Electronics',   129.99,  58.00,   87, TRUE),
('27" 4K Monitor',                  'ELEC-004', 'Electronics',   449.99, 220.00,   34, TRUE),
('Portable SSD 1TB',                'ELEC-005', 'Electronics',    89.99,  42.00,  195, TRUE),
('Webcam 1080p',                    'ELEC-006', 'Electronics',    49.99,  18.00,  210, TRUE),
('Wireless Mouse Ergonomic',        'ELEC-007', 'Electronics',    34.99,  12.00,  320, TRUE),
('Smart Watch Fitness Tracker',     'ELEC-008', 'Electronics',   199.99,  85.00,   63, TRUE),
('Noise Cancelling Earbuds',        'ELEC-009', 'Electronics',   149.99,  65.00,  108, TRUE),
('Laptop Stand Aluminum',           'ELEC-010', 'Electronics',    39.99,  14.00,  275, TRUE),
('Cotton Crew T-Shirt',             'CLTH-001', 'Clothing',       24.99,   8.00,  450, TRUE),
('Slim Fit Jeans',                  'CLTH-002', 'Clothing',       59.99,  22.00,  180, TRUE),
('Lightweight Rain Jacket',         'CLTH-003', 'Clothing',       89.99,  35.00,  120, TRUE),
('Merino Wool Sweater',             'CLTH-004', 'Clothing',       74.99,  30.00,   95, TRUE),
('Running Sneakers',                'CLTH-005', 'Clothing',      119.99,  48.00,  160, TRUE),
('Casual Hoodie',                   'CLTH-006', 'Clothing',       49.99,  18.00,  230, TRUE),
('Formal Dress Shirt',              'CLTH-007', 'Clothing',       44.99,  16.00,  140, TRUE),
('Cargo Shorts',                    'CLTH-008', 'Clothing',       34.99,  12.00,  200, TRUE),
('Winter Beanie',                   'CLTH-009', 'Clothing',       19.99,   6.00,  380, TRUE),
('Leather Belt',                    'CLTH-010', 'Clothing',       29.99,  10.00,  260, TRUE),
('Stainless Steel Water Bottle',    'HOME-001', 'Home & Kitchen', 24.99,   8.00,  500, TRUE),
('Non-Stick Frying Pan 12"',        'HOME-002', 'Home & Kitchen', 34.99,  14.00,  175, TRUE),
('French Press Coffee Maker',       'HOME-003', 'Home & Kitchen', 29.99,  10.00,  220, TRUE),
('Bamboo Cutting Board Set',        'HOME-004', 'Home & Kitchen', 19.99,   7.00,  310, TRUE),
('Vacuum Insulated Tumbler',        'HOME-005', 'Home & Kitchen', 27.99,   9.00,  280, TRUE),
('Scented Soy Candle Set',          'HOME-006', 'Home & Kitchen', 22.99,   6.00,  350, TRUE),
('Cotton Bath Towel Set',           'HOME-007', 'Home & Kitchen', 39.99,  15.00,  190, TRUE),
('Ceramic Dinner Plate Set',        'HOME-008', 'Home & Kitchen', 44.99,  18.00,  130, TRUE),
('Silicone Kitchen Utensil Set',    'HOME-009', 'Home & Kitchen', 26.99,   9.00,  240, TRUE),
('LED Desk Lamp Dimmable',          'HOME-010', 'Home & Kitchen', 32.99,  12.00,  200, TRUE),
('Yoga Mat Premium 6mm',            'SPRT-001', 'Sports',         29.99,  10.00,  280, TRUE),
('Resistance Bands Set',            'SPRT-002', 'Sports',         19.99,   6.00,  420, TRUE),
('Adjustable Dumbbell Pair',        'SPRT-003', 'Sports',        149.99,  65.00,   55, TRUE),
('Jump Rope Speed',                 'SPRT-004', 'Sports',         14.99,   4.00,  380, TRUE),
('Foam Roller 18"',                 'SPRT-005', 'Sports',         24.99,   8.00,  300, TRUE),
('Running Armband Phone Holder',    'SPRT-006', 'Sports',         16.99,   5.00,  350, TRUE),
('Insulated Gym Bag',               'SPRT-007', 'Sports',         39.99,  15.00,  180, TRUE),
('Cycling Gloves Padded',           'SPRT-008', 'Sports',         22.99,   8.00,  210, TRUE),
('Tennis Racket Intermediate',      'SPRT-009', 'Sports',         79.99,  32.00,   90, TRUE),
('Protein Shaker Bottle',           'SPRT-010', 'Sports',         12.99,   3.00,  500, TRUE),
('JavaScript: The Good Parts',      'BOOK-001', 'Books',          29.99,  12.00,  160, TRUE),
('Designing Data-Intensive Apps',   'BOOK-002', 'Books',          44.99,  20.00,  110, TRUE),
('Atomic Habits',                   'BOOK-003', 'Books',          16.99,   6.00,  340, TRUE),
('The Pragmatic Programmer',        'BOOK-004', 'Books',          49.99,  22.00,   85, TRUE),
('Clean Code',                      'BOOK-005', 'Books',          39.99,  16.00,  120, TRUE),
('Thinking Fast and Slow',          'BOOK-006', 'Books',          17.99,   7.00,  290, TRUE),
('Zero to One',                     'BOOK-007', 'Books',          15.99,   5.00,  310, TRUE),
('The Lean Startup',                'BOOK-008', 'Books',          18.99,   7.00,  250, TRUE),
('Deep Work',                       'BOOK-009', 'Books',          14.99,   5.00,  270, TRUE),
('Staff Engineer',                  'BOOK-010', 'Books',          34.99,  14.00,   75, FALSE);

-- ============================================================
-- Customers  (200 rows, generated via generate_series)
-- ============================================================

INSERT INTO customers (name, email, signup_date, lifetime_value)
SELECT
    'Customer ' || i,
    'customer' || i || '@example.com',
    CURRENT_DATE - (random() * 730)::int,
    0
FROM generate_series(1, 200) AS i;

-- ============================================================
-- Orders  (500 rows spread over the past 12 months)
-- ============================================================

INSERT INTO orders (customer_id, order_date, status, total_amount, shipping_cost)
SELECT
    (1 + (random() * 199)::int),
    NOW() - (random() * 365 || ' days')::interval - (random() * 24 || ' hours')::interval,
    CASE
        WHEN r < 0.05 THEN 'cancelled'
        WHEN r < 0.15 THEN 'returned'
        WHEN r < 0.25 THEN 'pending'
        WHEN r < 0.40 THEN 'shipped'
        ELSE 'delivered'
    END,
    0,
    ROUND((random() * 20 + 5)::numeric, 2)
FROM (
    SELECT generate_series(1, 500), random() AS r
) AS sub(i, r);

-- ============================================================
-- Order Items  (~1500 rows, 1-5 items per order)
-- ============================================================

DO $$
DECLARE
    oid   INT;
    n     INT;
    pid   INT;
    qty   INT;
    price NUMERIC;
BEGIN
    FOR oid IN SELECT order_id FROM orders LOOP
        n := 1 + floor(random() * 5)::int;  -- 1-5 items per order
        FOR i IN 1..n LOOP
            pid   := 1 + floor(random() * 50)::int;
            qty   := 1 + floor(random() * 4)::int;
            SELECT p.price INTO price FROM products p WHERE p.product_id = pid;
            IF price IS NOT NULL THEN
                INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
                VALUES (oid, pid, qty, price, ROUND(qty * price, 2));
            END IF;
        END LOOP;
    END LOOP;
END $$;

-- ============================================================
-- Back-fill order totals from line items
-- ============================================================

UPDATE orders o
SET total_amount = sub.item_total + o.shipping_cost
FROM (
    SELECT order_id, COALESCE(SUM(line_total), 0) AS item_total
    FROM order_items
    GROUP BY order_id
) sub
WHERE o.order_id = sub.order_id;

-- ============================================================
-- Back-fill customer lifetime_value from delivered orders
-- ============================================================

UPDATE customers c
SET lifetime_value = sub.ltv
FROM (
    SELECT customer_id, COALESCE(SUM(total_amount), 0) AS ltv
    FROM orders
    WHERE status NOT IN ('cancelled', 'returned')
    GROUP BY customer_id
) sub
WHERE c.customer_id = sub.customer_id;

COMMIT;
