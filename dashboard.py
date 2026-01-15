import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from sqlalchemy import create_engine, text

# --------------------------------------------------------------------------
# 1. PAGE SETUP & LOGIN GATEKEEPER
# --------------------------------------------------------------------------
st.set_page_config(page_title="Sales System", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def login():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.header("🔒 System Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Log in", use_container_width=True):
            if user == st.secrets["admin"]["username"] and pwd == st.secrets["admin"]["password"]:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ Access Denied")

if not st.session_state["logged_in"]:
    login()
    st.stop()

# --------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# --------------------------------------------------------------------------
# Database Connection
def get_engine():
    return create_engine(st.secrets["postgres"]["url"])

# Fetch Data for Dashboard
@st.cache_data
def get_sales_data():
    conn = psycopg2.connect(st.secrets["postgres"]["url"])
    df = pd.read_sql("SELECT * FROM monthly_sales;", conn)
    conn.close()
    df['sale_day'] = pd.to_datetime(df['sale_day'])
    return df

# --------------------------------------------------------------------------
# 3. PAGE: DASHBOARD (The Viewer)
# --------------------------------------------------------------------------
def show_dashboard():
    st.title("📊 Monthly Sales Live Dashboard")
    df = get_sales_data()

    if df.empty:
        st.warning("No data available. Go to the Admin Panel to upload data.")
        return

    # --- Sidebar Filters ---
    st.sidebar.header("🔍 Filters")
    min_date, max_date = df['sale_day'].min(), df['sale_day'].max()
    date_range = st.sidebar.date_input("Date Range", value=(min_date, max_date))
    
    region_list = df['shipping_region'].unique().tolist()
    sel_regions = st.sidebar.multiselect("Region", region_list, default=region_list)
    
    product_list = df['product_title'].unique().tolist()
    sel_products = st.sidebar.multiselect("Product", product_list, default=product_list)

    # --- Filtering Logic ---
    mask = (
        (df['sale_day'].dt.date >= date_range[0]) &
        (df['sale_day'].dt.date <= date_range[1]) &
        (df['shipping_region'].isin(sel_regions)) &
        (df['product_title'].isin(sel_products))
    )
    filtered_df = df[mask]

    # --- Metrics ---
    col1, col2 = st.columns(2)
    col1.metric("💰 Total Revenue", f"₹{filtered_df['net_sales'].sum():,.2f}")
    col2.metric("📦 Total Orders", f"{filtered_df['quantity_order'].sum()}")
    st.markdown("---")

    # --- Charts ---
    c1, c2 = st.columns(2)
    with c1:
        reg_sales = filtered_df.groupby('shipping_region')['net_sales'].sum().reset_index()
        st.plotly_chart(px.bar(reg_sales, x='shipping_region', y='net_sales', title="Regional Sales"), use_container_width=True)
    with c2:
        top_prod = filtered_df.groupby('product_title')['quantity_order'].sum().nlargest(5).reset_index()
        st.plotly_chart(px.pie(top_prod, names='product_title', values='quantity_order', title="Top Products"), use_container_width=True)

# --------------------------------------------------------------------------
# 4. PAGE: ADMIN PANEL (The Manager)
# --------------------------------------------------------------------------
def show_admin():
    st.title("⚙️ Admin Panel")
    st.markdown("Use this panel to **Upload Data**, **Inspect Tables**, and **Manage the System**.")
    
    tab1, tab2 = st.tabs(["📤 Upload Data", "📋 Database Inspector"])

    # --- TAB 1: UPLOADER ---
    with tab1:
        st.subheader("Add New Records")
        upload_type = st.selectbox("Select Table to Update", ["monthly_sales", "amazon_ads"])
        uploaded_file = st.file_uploader(f"Upload CSV for {upload_type}", type=["csv"])
        
        if uploaded_file:
            st.info(f"Preparing to upload to table: `{upload_type}`...")
            if st.button("🚀 Confirm Upload"):
                try:
                    engine = get_engine()
                    df_new = pd.read_csv(uploaded_file)
                    
                    # Logic for Amazon Ads mapping (same as before)
                    if upload_type == "amazon_ads":
                        map_dict = {
                            'Products': 'products', 'Status': 'status', 'Ad Type': 'ad_type', 
                            'Sponsored': 'sponsored', 'Sales(INR)': 'sales_inr', 'ROAS': 'roas', 
                            'Conversion Rate': 'conversion_rate', 'Impressions': 'impressions', 
                            'Clicks': 'clicks', 'CTR': 'ctr', 'Spend(INR)': 'spend_inr', 
                            'CPC(INR)': 'cpc_inr', 'Orders': 'orders', 'ACOS': 'acos', 
                            'NTB Orders': 'ntb_orders', '% of Orders': 'percent_of_orders', 
                            'NTB Sales(INR)': 'ntb_sales_inr', '% of Sales': 'percent_of_sales', 
                            'Viewable Impressions': 'viewable_impressions'
                        }
                        # Normalize columns
                        df_new = df_new.rename(columns=map_dict)
                        valid = [c for c in map_dict.values() if c in df_new.columns]
                        df_new = df_new[valid]

                    # Upload
                    df_new.to_sql(upload_type, engine, if_exists="append", index=False)
                    st.success(f"✅ Successfully added {len(df_new)} rows to {upload_type}!")
                    st.cache_data.clear() # Force dashboard to refresh next time
                
                except Exception as e:
                    st.error(f"Upload Failed: {e}")

    # --- TAB 2: INSPECTOR ---
    with tab2:
        st.subheader("View Full Database Tables")
        table_view = st.selectbox("Choose Table to View", ["monthly_sales", "amazon_ads"])
        
        if st.button(f"Load Data for {table_view}"):
            try:
                conn = psycopg2.connect(st.secrets["postgres"]["url"])
                # Limit to 100 rows for speed, or remove LIMIT to see all
                view_df = pd.read_sql(f"SELECT * FROM {table_view} LIMIT 500;", conn)
                conn.close()
                
                st.write(f"Showing first 500 rows of `{table_view}`")
                st.dataframe(view_df)
                
                # Download Button for the Admin
                csv = view_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Full Table Dump", csv, f"{table_view}_dump.csv", "text/csv")
            except Exception as e:
                st.error(f"Error reading table: {e}")

# --------------------------------------------------------------------------
# 5. MAIN NAVIGATION LOGIC
# --------------------------------------------------------------------------
# Sidebar Navigation
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Go to:", ["📊 Dashboard", "⚙️ Admin Panel"])
    st.markdown("---")
    if st.button("Log Out"):
        st.session_state["logged_in"] = False
        st.rerun()

# Router
if page == "📊 Dashboard":
    show_dashboard()
else:
    show_admin()