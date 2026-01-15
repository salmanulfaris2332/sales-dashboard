from sqlalchemy import create_engine
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px

# --- PAGE SETUP ---
st.set_page_config(page_title="Sales Dashboard", layout="wide")
st.title("📊 Monthly Sales Live Dashboard")

# --- DATABASE CONNECTION ---
@st.cache_data
def get_data():
    try:
        # Use st.secrets to get the connection string securely
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
df = get_data()

if not df.empty:
    st.sidebar.header("📂 Data Upload")
    uploaded_file = st.sidebar.file_uploader("Upload New Sales CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            # 1. Read the file
            ad_df = pd.read_csv(uploaded_file)
            
            # 2. Rename columns to match our SQL table exactly
            # We use a dictionary to map "CSV Header" -> "SQL Column"
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
            
            # Rename and keep only the columns we need
            ad_df = ad_df.rename(columns=column_map)
            ad_df = ad_df[column_map.values()]

            # 3. Connect and Append to Database
            # We use SQLAlchemy here because it's much faster for writing data
            engine = create_engine(st.secrets["postgres"]["url"])
            ad_df.to_sql("amazon_ads", engine, if_exists="append", index=False)
            
            st.sidebar.success(f"✅ Success! {len(ad_df)} rows uploaded to 'amazon_ads'.")
            
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
        
    st.sidebar.markdown("---")
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Filter Data")
    
    # 1. Date Filter
    min_date = df['sale_day'].min()
    max_date = df['sale_day'].max()
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # 2. Region Filter
    region_list = df['shipping_region'].unique().tolist()
    selected_regions = st.sidebar.multiselect(
        "Select Region",
        options=region_list,
        default=region_list # Select all by default
    )

    # 3. Product Filter
    product_list = df['product_title'].unique().tolist()
    selected_products = st.sidebar.multiselect(
        "Select Product",
        options=product_list,
        default=product_list
    )

    # --- APPLY FILTERS ---
    # We create a new "filtered_df" that only keeps what matches your choices
    mask = (
        (df['sale_day'].dt.date >= date_range[0]) &
        (df['sale_day'].dt.date <= date_range[1]) &
        (df['shipping_region'].isin(selected_regions)) &
        (df['product_title'].isin(selected_products))
    )
    filtered_df = df[mask]

    # --- TOP METRICS (Based on Filtered Data) ---
    total_revenue = filtered_df['net_sales'].sum()
    total_orders = filtered_df['quantity_order'].sum()
    
    col1, col2 = st.columns(2)
    col1.metric("💰 Revenue (Filtered)", f"₹{total_revenue:,.2f}")
    col2.metric("📦 Orders (Filtered)", f"{total_orders}")

    st.markdown("---")

    # --- CHARTS (Based on Filtered Data) ---
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
                                 title="Top Products Share", hole=0.4)
            st.plotly_chart(fig_product, use_container_width=True)

    # --- RAW DATA TABLE ---
    st.subheader("📋 Detailed Data View")
    st.write(f"Showing {len(filtered_df)} rows based on your filters")
    st.dataframe(filtered_df)
    # --- DOWNLOAD BUTTON ---
    # 1. Convert the filtered data to CSV format in memory
    csv = filtered_df.to_csv(index=False).encode('utf-8')

    # 2. Create the download button
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv,
        file_name="my_filtered_sales.csv",
        mime="text/csv",
    )

else:
    st.warning("No data found.")