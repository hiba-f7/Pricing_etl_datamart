-- View 1: Regional Margin & Revenue Summary
CREATE OR REPLACE VIEW vw_regional_pricing_performance AS
SELECT 
    f.customer_region,
    COUNT(f.transaction_id) AS total_orders,
    SUM(f.units_sold) AS total_units_sold,
    ROUND(AVG(f.discount_pct) * 100, 2) AS avg_discount_pct,
    ROUND(SUM(f.total_net_revenue), 2) AS total_revenue
FROM fact_pricing_sales f
GROUP BY f.customer_region
ORDER BY total_revenue DESC;

-- View 2: Product Catalog Price Realization Analysis
CREATE OR REPLACE VIEW vw_product_price_realization AS
SELECT 
    d.category,
    d.part_number,
    d.standard_list_price,
    SUM(f.units_sold) AS total_volume_sold,
    ROUND(SUM(f.total_net_revenue), 2) AS gross_revenue,
    ROUND(AVG(f.discounted_price), 2) AS avg_realized_price,
    ROUND((1.0 - (AVG(f.discounted_price) / d.standard_list_price)) * 100, 2) AS effective_margin_erosion_pct
FROM fact_pricing_sales f
JOIN dim_parts d ON f.part_number = d.part_number
GROUP BY d.category, d.part_number, d.standard_list_price
ORDER BY gross_revenue DESC;