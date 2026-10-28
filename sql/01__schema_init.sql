-- Star Schema DDL Definition

DROP TABLE IF EXISTS fact_pricing_sales CASCADE;
DROP TABLE IF EXISTS dim_parts CASCADE;

-- 1. Parts Dimension Table
CREATE TABLE dim_parts (
    part_number VARCHAR(50) PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    standard_list_price NUMERIC(12, 2) NOT NULL
);

-- 2. Fact Sales Data Mart Table
CREATE TABLE fact_pricing_sales (
    transaction_id VARCHAR(50) PRIMARY KEY,
    part_number VARCHAR(50) NOT NULL REFERENCES dim_parts(part_number),
    list_price NUMERIC(12, 2) NOT NULL,
    discount_pct NUMERIC(5, 4) NOT NULL,
    discounted_price NUMERIC(12, 2) NOT NULL,
    units_sold INT NOT NULL,
    total_net_revenue NUMERIC(14, 2) NOT NULL,
    sale_date DATE NOT NULL,
    customer_region VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Composite Analytical Performance Indexes
CREATE INDEX idx_pricing_part_region ON fact_pricing_sales (part_number, customer_region);
CREATE INDEX idx_pricing_sale_date ON fact_pricing_sales (sale_date);