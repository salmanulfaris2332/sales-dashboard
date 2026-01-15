import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from sqlalchemy import create_engine

# --------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# --------------------------------------------------------------------------
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Monthly Sales Live Dashboard")

# --------------------------------------------------------------------------
# 2. LOGIN AUTHENTICATION (THE GATEKEEPER)
# --------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def login():
    st.header("🔒 Founders Login")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    
    if st.button("Log in"):
        # Check against secrets
        if user == st.secrets["admin"]["username"] and pwd == st.secrets["admin"]["password"]:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect Username or Password")

# Stop the app here if not logged in
if not st.session_state["logged_in"]:
    login()
    st.stop() 

# --------------------------------------------------------------------------
# 3. DATABASE CONNECTION & DATA FETCHING
# --------------------------------------------------------------------------
@st.cache_data
def get_data():
    try:
        conn = psycopg2.connect(st.secrets["postgres"]["url"])
        query = "SELECT * FROM monthly_sales;"
        df = pd.read_sql(query, conn)
        conn.close()
        
        # Ensure sale_day is a real Date object
        df['sale_day'] = pd.to_datetime(df['sale_day'])
        return df
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return pd.DataFrame()

# Load the data immediately after login
df = get_data()

# --------------------------------------------------------------------------
# 4. SIDEBAR: DATA UPLOAD & FILTERS
# --------------------------------------------------------------------------
st.sidebar.header("📂 Data Management")

# A. Data Uploader (Supports Sales and Amazon Ads)
upload_type = st.sidebar.selectbox("Select Upload Type", ["Monthly Sales", "Amazon Ads"])
uploaded_file = st.sidebar.file_uploader(f"Upload {upload_type} CSV", type=["csv"])

if uploaded_file is not None:
    try:
        engine = create_engine(st.secrets["postgres"]["url"])
        
        if upload_type == "Monthly Sales":
            # Simple append for sales data
            new_data = pd.read_csv(uploaded_file)
            new_data.to_sql("monthly_sales", engine, if_exists="append", index=False)
            st.sidebar.success("✅ Sales Data Uploaded!")
            st.cache_data.clear() # Clear cache so new data shows up

        elif upload_type == "Amazon Ads":
            # Complex mapping for Amazon data
            ad_df = pd.read_csv(uploaded_file)
            column_map = {
                'Products': 'products', 'Status': 'status', 'Ad Type': 'ad_type', 
                'Sponsored': 'sponsored', 'Sales(INR)': 'sales_inr', 'ROAS': 'roas', 
                'Conversion Rate': 'conversion_rate', 'Impressions': 'impressions', 
                'Clicks': 'clicks', 'CTR': 'ctr', 'Spend(INR)': 'spend_inr', 
                'CPC(INR)': 'cpc_inr', 'Orders': 'orders', 'ACOS': 'acos', 
                'NTB Orders': 'ntb_orders', '% of Orders': 'percent_of_orders', 
                'NTB Sales(INR)': 'ntb_sales_inr', '% of Sales': 'percent_of_sales', 
                'Viewable Impressions': 'viewable_impressions'
            }
            # Rename and filter columns
            ad_df = ad_df.rename(columns=column_map)
            # Only keep columns that exist in our mapping
            valid_cols = [c for c in column_map.values() if c in ad_df.columns]
            ad_df = ad_df[valid_cols]
            
            ad_df.to_sql("amazon_ads", engine, if_exists="append", index=False)
            st.sidebar.success("✅ Amazon Ads Data Uploaded!")

    except Exception as e:
        st.sidebar.error(f"Upload Error: {e}")

st.sidebar.markdown("---")

# --------------------------------------------------------------------------
# 5. MAIN DASHBOARD LOGIC
# --------------------------------------------------------------------------
if not df.empty:
    # --- FILTERS ---
    st.sidebar.header("🔍 Filter Dashboard")
    
    min_date = df['sale_day'].min()
    max_date = df['sale_day'].max()
    date_range = st.sidebar.date_input("Date Range", value=(min_date, max_date))

    region_list = df['shipping_region'].unique().tolist()
    selected_regions = st.sidebar.multiselect("Region", options=region_list, default=region_list)

    product_list = df['product_title'].unique().tolist()
    selected_products = st.sidebar.multiselect("Product", options=product_list, default=product_list)

    # --- APPLY FILTERS ---
    mask = (
        (df['sale_day'].dt.date >= date_range[0]) &
        (df['sale_day'].dt.date <= date_range[1]) &
        (df['shipping_region'].isin(selected_regions)) &
        (df['product_title'].isin(selected_products))
    )
    filtered_df = df[mask]

    # --- METRICS ---
    total_revenue = filtered_df['net_sales'].sum()
    total_orders = filtered_df['quantity_order'].sum()
    
    col1, col2 = st.columns(2)
    col1.metric("💰 Total Revenue", f"₹{total_revenue:,.2f}")
    col2.metric("📦 Total Orders", f"{total_orders}")

    st.markdown("---")

    # --- CHARTS ---
    col3, col4 = st.columns(2)
    
    with col3:
        if not filtered_df.empty:
            region_sales = filtered_df.groupby('shipping_region')['net_sales'].sum().reset_index()
            fig_region = px.bar(region_sales, x='shipping_region', y='net_sales', 
                                title="Sales by Region", template="plotly_dark")
            st.plotly_chart(fig_region, use_container_width=True)
    
    with col4:
        if not filtered_df.empty:
            top_products = filtered_df.groupby('product_title')['quantity_order'].sum().nlargest(5).reset_index()
            fig_product = px.pie(top_products, names='product_title', values='quantity_order', 
                                 title="Top 5 Products", hole=0.4)
            st.plotly_chart(fig_product, use_container_width=True)

    # --- RAW DATA VIEW ---
    with st.expander("📋 View Detailed Data"):
        st.dataframe(filtered_df)
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Filtered CSV", data=csv, file_name="sales_data.csv", mime="text/csv")

else:
    st.warning("⚠️ No data found in the 'monthly_sales' table. Please upload data via the sidebar!")