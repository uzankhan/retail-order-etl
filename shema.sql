-- ============================================
-- Retail Order ETL — Database Schema
-- ============================================

CREATE SCHEMA IF NOT EXISTS lab;

CREATE TABLE IF NOT EXISTS lab.orders (
    order_id VARCHAR(50) PRIMARY KEY,
    order_date DATE NOT NULL,
    city VARCHAR(100),
    category VARCHAR(100),
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price > 0),
    status VARCHAR(50) NOT NULL,
    revenue DECIMAL(12,2),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_orders_date ON lab.orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_category ON lab.orders(category);
CREATE INDEX IF NOT EXISTS idx_orders_status ON lab.orders(status);

-- Reporting view
CREATE OR REPLACE VIEW lab.daily_sales AS
SELECT
    order_date,
    category,
    status,
    COUNT(*) AS total_orders,
    SUM(quantity) AS total_quantity,
    SUM(revenue) AS total_revenue
FROM lab.orders
GROUP BY order_date, category, status;

-- ETL user
CREATE USER sales_etl WITH PASSWORD 'CHANGE_ME';
GRANT USAGE ON SCHEMA lab TO sales_etl;
GRANT SELECT, INSERT, UPDATE, DELETE ON lab.orders TO sales_etl;