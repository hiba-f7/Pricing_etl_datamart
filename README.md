# Automated Pricing Telemetry ETL & Star Schema Data Mart

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end telemetry pricing pipeline and dimensional data mart designed to ingest, clean, validate, and load spare parts sales feeds into an enterprise Star Schema. Built to prevent margin erosion via automated discount clamping, median pricing imputations, and idempotent loads.

---

## Architecture Overview

```
Raw CSV / Telemetry Feed (data/raw_pricing_feed.csv)
                      │
                      ▼
        Python Automated ETL Engine (etl.py)
   ┌──────────────────────────────────────────────┐
   │ - Group-level median list price imputation   │
   │ - Business rule discount clamping [0%, 50%]  │
   │ - Unit & Revenue derived calculations        │
   │ - Idempotent cascade staging sync            │
   └──────────────────────┬───────────────────────┘
                          │ SQLAlchemy / Psycopg2
                          ▼
            PostgreSQL Dimensional Data Mart
   ┌───────────────────────┐     1:N     ┌────────────────────────┐
   │       dim_parts       │ ──────────< │   fact_pricing_sales   │
   │ (Part Master, Prices) │             │ (Transactions, Margin) │
   └───────────────────────┘             └───────────┬────────────┘
                                                     │
                                                     ▼
                                        Analytical Reporting Views
                                      - vw_regional_pricing_performance
                                      - vw_product_price_realization
```

---

## Key Technical Features

1. **Defensive Data Ingestion & Imputation**:
   - Imputes missing catalog prices using category/part-level medians.
   - Enforces business boundaries on discounts: strictly clamped to $[0.00, 0.50]$ to prevent rogue negative prices or excessive promotional margin leakage.
   - Type coercion and default handling on transactional unit quantities.

2. **Dimensional Star Schema Design**:
   - `dim_parts`: Primary-keyed dimension catalog tracking standard list pricing and part classifications.
   - `fact_pricing_sales`: Granular transaction records referencing `dim_parts` with composite B-Tree indexes (`idx_pricing_part_region`, `idx_pricing_sale_date`) optimized for analytical aggregations.

3. **Production Idempotency & ACID Transactions**:
   - Uses SQLAlchemy engine context managers (`with engine.begin()`) ensuring atomic batch execution.
   - Implements automated stage truncates (`TRUNCATE... CASCADE`) to guarantee idempotent, duplicate-safe pipeline re-runs without violating primary key constraints.

4. **Pre-Aggregated Business Intelligence Views**:
   - `vw_regional_pricing_performance`: Aggregates order volumes, regional gross revenue, and effective average discount realization.
   - `vw_product_price_realization`: Analyzes margin erosion percentage across heavy equipment catalog tiers.

---

## Project Structure

```text
Pricing_etl_datamart/
├── data/
│   └── raw_pricing_feed.csv       # Raw transactional ingestion feed
├── sql/
│   ├── 01_schema_init.sql         # DDL tables, constraints, and indexes
│   └── 02_analytical_views.sql    # Analytical SQL reporting views
├── etl.py                         # Modular Python extraction, transformation & loading
├── requirements.txt               # Pipeline dependencies
├── .gitignore                     # Git tracking exclusions
└── README.md                      # Project documentation
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- PostgreSQL (running locally or remotely)
- DBeaver or `psql` client

### 2. Database Initialization
Execute the schema creation script inside your PostgreSQL instance:
```bash
psql -U postgres -d pricing_analytics -f sql/01_schema_init.sql
psql -U postgres -d pricing_analytics -f sql/02_analytical_views.sql
```
*(Alternatively, execute both `.sql` scripts inside DBeaver connected to `pricing_analytics`)*.

### 3. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/hiba-f7/Pricing_etl_datamart.git
cd Pricing_etl_datamart
pip install -r requirements.txt
```

### 4. Configuration & Execution
Set your database credentials via environment variables (or leave defaults for local instances):
```bash
# Windows Command Prompt
set DB_USER=postgres
set DB_PASS=your_password
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=pricing_analytics

# Execute ETL Pipeline
python etl.py
```

---

## Analytical Insights Sample

Sample query querying the generated dimensional views:

```sql
SELECT 
    category,
    part_number,
    total_volume_sold,
    gross_revenue,
    avg_realized_price,
    effective_margin_erosion_pct
FROM vw_product_price_realization
ORDER BY gross_revenue DESC;
```

---

## License
All Rights Reserved © 2026 HIBA FAHIMA P. For educational evaluation purposes only.
