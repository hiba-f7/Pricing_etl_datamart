import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from io import StringIO

st.set_page_config(
    page_title="Pricing Analytics Data Mart",
    page_icon="📊",
    layout="wide"
)

raw_csv = """transaction_id,part_number,category,list_price,discount_pct,units_sold,sale_date,customer_region
TXN1001,CAT-ENG-101,Engine Systems,1250.00,0.10,4,2026-08-01,EMEA
TXN1002,CAT-HYD-202,Hydraulics,850.50,0.05,10,2026-08-02,Americas
TXN1003,CAT-ENG-101,Engine Systems,1250.00,0.15,2,2026-08-03,APAC
TXN1004,CAT-ELE-303,Electrical,320.00,0.00,15,2026-08-03,EMEA
TXN1005,CAT-UND-404,Undercarriage,,0.20,1,2026-08-04,EMEA
TXN1006,CAT-HYD-202,Hydraulics,850.50,0.08,5,2026-08-05,Americas
TXN1007,CAT-GET-505,Ground Engaging,2100.00,-0.05,3,2026-08-06,APAC
TXN1008,CAT-ENG-101,Engine Systems,1250.00,0.75,1,2026-08-07,Americas
TXN1009,CAT-ELE-303,Electrical,320.00,0.02,,2026-08-08,EMEA
TXN1010,CAT-UND-404,Undercarriage,4200.00,0.12,2,2026-08-09,Americas
TXN1011,CAT-GET-505,Ground Engaging,2100.00,0.10,6,2026-08-10,APAC
TXN1012,CAT-DRV-606,Drivetrain,3150.00,0.18,3,2026-08-11,EMEA
TXN1013,CAT-DRV-606,Drivetrain,3150.00,0.05,4,2026-08-12,Americas
TXN1014,CAT-HYD-202,Hydraulics,850.50,0.10,8,2026-08-13,APAC
TXN1015,CAT-ELE-303,Electrical,320.00,0.00,20,2026-08-14,Americas"""

@st.cache_resource
def get_engine():
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASS", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "pricing_analytics")

    # 1. Check local PostgreSQL
    try:
        pg_engine = create_engine(
            f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}",
            connect_args={"connect_timeout": 2}
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return pg_engine, "PostgreSQL (Production Data Mart)"
    except Exception:
        # 2. File-based SQLite fallback (shared across threads without locking)
        db_path = "pricing_mart.db"
        sqlite_engine = create_engine(f"sqlite:///{db_path}")

        csv_path = os.path.join("data", "raw_pricing_feed.csv")
        if os.path.exists(csv_path):
            raw_df = pd.read_csv(csv_path)
        else:
            raw_df = pd.read_csv(StringIO(raw_csv))

        # ETL data cleaning & business rules
        raw_df["list_price"] = raw_df.groupby("part_number")["list_price"].transform(lambda s: s.fillna(s.median()))
        raw_df["discount_pct"] = pd.to_numeric(raw_df["discount_pct"], errors="coerce").fillna(0.0)
        raw_df["discount_pct"] = raw_df["discount_pct"].apply(lambda d: max(0.0, min(float(d), 0.50)))
        raw_df["units_sold"] = pd.to_numeric(raw_df["units_sold"], errors="coerce").fillna(1).astype(int)
        raw_df["discounted_price"] = (raw_df["list_price"] * (1.0 - raw_df["discount_pct"])).round(2)
        raw_df["total_net_revenue"] = (raw_df["discounted_price"] * raw_df["units_sold"]).round(2)
        raw_df["sale_date"] = pd.to_datetime(raw_df["sale_date"]).dt.strftime("%Y-%m-%d")
        raw_df["customer_region"] = raw_df["customer_region"].fillna("UNKNOWN").str.upper()

        dim_parts = (
            raw_df[["part_number", "category", "list_price"]]
            .drop_duplicates(subset=["part_number"])
            .rename(columns={"list_price": "standard_list_price"})
        )
        fact_sales = raw_df[[
            "transaction_id", "part_number", "list_price", "discount_pct",
            "discounted_price", "units_sold", "total_net_revenue", "sale_date", "customer_region"
        ]]

        with sqlite_engine.begin() as conn:
            dim_parts.to_sql("dim_parts", conn, index=False, if_exists="replace")
            fact_sales.to_sql("fact_pricing_sales", conn, index=False, if_exists="replace")

        return sqlite_engine, "SQLite File-Backed Data Mart (Cloud Ready)"

engine, engine_type = get_engine()

# Dashboard Header
st.title("Enterprise Pricing Analytics & Star Schema Data Mart")
st.caption(f"Connected Backend: **{engine_type}** | Schema: `Star Schema (dim_parts, fact_pricing_sales)`")

# Top KPI Metric Cards
q_kpis = text("""
SELECT 
    COUNT(transaction_id) AS total_orders,
    SUM(units_sold) AS total_units_sold,
    ROUND(SUM(total_net_revenue), 2) AS total_net_revenue,
    ROUND(AVG(discount_pct) * 100, 2) AS avg_discount_pct
FROM fact_pricing_sales;
""")

with engine.connect() as conn:
    df_kpis = pd.read_sql(q_kpis, conn)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Net Revenue", f"${df_kpis['total_net_revenue'][0]:,.2f}")
kpi2.metric("Total Units Sold", f"{df_kpis['total_units_sold'][0]:,}")
kpi3.metric("Total Invoiced Orders", f"{df_kpis['total_orders'][0]}")
kpi4.metric("Avg Portfolio Discount", f"{df_kpis['avg_discount_pct'][0]:.2f}%")

st.markdown("---")

# Visualizations & Regional Performance
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Regional Performance Summary")
    q_region = text("""
    SELECT 
        customer_region,
        COUNT(transaction_id) AS total_orders,
        SUM(units_sold) AS total_units_sold,
        ROUND(AVG(discount_pct) * 100, 2) AS avg_discount_pct,
        ROUND(SUM(total_net_revenue), 2) AS total_revenue
    FROM fact_pricing_sales
    GROUP BY customer_region
    ORDER BY total_revenue DESC;
    """)
    with engine.connect() as conn:
        df_region = pd.read_sql(q_region, conn)
    st.dataframe(df_region, use_container_width=True)

with col_right:
    st.subheader("Net Revenue by Geographic Region")
    st.bar_chart(df_region.set_index("customer_region")["total_revenue"])

st.markdown("---")

# Product Catalog Realization
st.subheader("Product Catalog Price Realization & Margin Analysis")
q_product = text("""
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
""")
with engine.connect() as conn:
    df_product = pd.read_sql(q_product, conn)
st.dataframe(df_product, use_container_width=True)
