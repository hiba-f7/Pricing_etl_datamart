import os
import sys
import logging
import pandas as pd
from sqlalchemy import create_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Database Configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")  
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "pricing_analytics")

CSV_PATH = os.path.join("data", "raw_pricing_feed.csv")

def extract(file_path: str) -> pd.DataFrame:
    """Extract raw feed from CSV or incoming data source."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Source file not found at: {file_path}")
    logging.info(f"Extracting data from {file_path}...")
    df = pd.read_csv(file_path)
    logging.info(f"Successfully extracted {len(df)} rows.")
    return df

def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean, impute, bound discounts, and split into Star Schema models."""
    logging.info("Starting data cleaning and transformation pipeline...")
    
    # 1. Impute missing list prices using category/part median
    df["list_price"] = df.groupby("part_number")["list_price"].transform(
        lambda s: s.fillna(s.median())
    )
    
    # 2. Bound discount percentages [0.00, 0.50]
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0.0)
    df["discount_pct"] = df["discount_pct"].apply(lambda d: max(0.0, min(float(d), 0.50)))
    
    # 3. Clean units sold
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce").fillna(1).astype(int)
    
    # 4. KPI Calculations
    df["discounted_price"] = (df["list_price"] * (1.0 - df["discount_pct"])).round(2)
    df["total_net_revenue"] = (df["discounted_price"] * df["units_sold"]).round(2)
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.date
    df["customer_region"] = df["customer_region"].fillna("UNKNOWN").str.upper()

    # 5. Build Dimension: dim_parts
    dim_parts = (
        df[["part_number", "category", "list_price"]]
        .drop_duplicates(subset=["part_number"])
        .rename(columns={"list_price": "standard_list_price"})
        .copy()
    )

    # 6. Build Fact: fact_pricing_sales
    fact_sales = df[[
        "transaction_id", "part_number", "list_price", "discount_pct",
        "discounted_price", "units_sold", "total_net_revenue", "sale_date", "customer_region"
    ]].copy()

    logging.info("Transformation finished: Dimension & Fact tables structured.")
    return dim_parts, fact_sales

def load(dim_parts: pd.DataFrame, fact_sales: pd.DataFrame) -> None:
    """Load transformed datasets into PostgreSQL Star Schema safely."""
    conn_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(conn_string)
    
    logging.info("Connecting to PostgreSQL and syncing records...")
    with engine.begin() as conn:
        # 1. Truncate existing staging data to allow clean re-runs
        conn.exec_driver_sql("TRUNCATE TABLE fact_pricing_sales, dim_parts CASCADE;")
        
        # 2. Re-load clean dimensional master
        dim_parts.to_sql("dim_parts", conn, if_exists="append", index=False)
        
        # 3. Load fact telemetry
        fact_sales.to_sql("fact_pricing_sales", conn, if_exists="append", index=False)
    
    logging.info("Load complete: All records synced to 'pricing_analytics' successfully.")

if __name__ == "__main__":
    raw_df = extract(CSV_PATH)
    dim, fact = transform(raw_df)
    load(dim, fact)