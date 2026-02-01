"""
FoodJoint Order Management Dashboard

A standalone web-based dashboard to view and search orders from the database.

To run:
    pip install streamlit
    streamlit run dashboard.py

Or with virtual environment:
    ./ai/bin/pip install streamlit
    ./ai/bin/streamlit run dashboard.py
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="FoodJoint Dashboard",
    page_icon="FJ",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database path
DB_PATH = Path(__file__).parent / "database" / "orders.db"
MENU_PATH = Path(__file__).parent / "database" / "food_menu.json"


@st.cache_data(ttl=5)  # Cache for 5 seconds
def get_all_orders():
    """Fetch all orders from database"""
    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT order_id, customer_name,
               total_amount, created_at, status
        FROM orders
        ORDER BY created_at DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=5)
def get_order_details(order_id):
    """Fetch detailed information for a specific order"""
    conn = sqlite3.connect(str(DB_PATH))

    # Get order info
    order_query = """
        SELECT * FROM orders WHERE order_id = ?
    """
    order_df = pd.read_sql_query(order_query, conn, params=(order_id,))

    # Get order items
    items_query = """
        SELECT item_name, quantity, item_price, addons
        FROM order_items
        WHERE order_id = ?
    """
    items_df = pd.read_sql_query(items_query, conn, params=(order_id,))

    conn.close()
    return order_df, items_df


def search_orders(search_term, search_by):
    """Search orders by different criteria"""
    conn = sqlite3.connect(str(DB_PATH))

    if search_by == "Order ID":
        query = """
            SELECT order_id, customer_name,
                   total_amount, created_at, status
            FROM orders
            WHERE order_id LIKE ?
            ORDER BY created_at DESC
        """
        params = (f"%{search_term}%",)
    else:  # Customer Name
        query = """
            SELECT order_id, customer_name,
                   total_amount, created_at, status
            FROM orders
            WHERE customer_name LIKE ?
            ORDER BY created_at DESC
        """
        params = (f"%{search_term}%",)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_statistics():
    """Calculate various statistics from the database"""
    conn = sqlite3.connect(str(DB_PATH))

    # Total orders
    total_orders = pd.read_sql_query(
        "SELECT COUNT(*) as count FROM orders", conn
    )['count'][0]

    # Total revenue
    total_revenue = pd.read_sql_query(
        "SELECT SUM(total_amount) as total FROM orders", conn
    )['total'][0] or 0

    # Average order value
    avg_order = pd.read_sql_query(
        "SELECT AVG(total_amount) as avg FROM orders", conn
    )['avg'][0] or 0

    # Today's orders
    today_orders = pd.read_sql_query(
        """
        SELECT COUNT(*) as count FROM orders
        WHERE date(created_at) = date('now')
        """, conn
    )['count'][0]

    # Today's revenue
    today_revenue = pd.read_sql_query(
        """
        SELECT SUM(total_amount) as total FROM orders
        WHERE date(created_at) = date('now')
        """, conn
    )['total'][0] or 0

    # Top items
    top_items = pd.read_sql_query(
        """
        SELECT item_name, SUM(quantity) as total_quantity,
               COUNT(*) as order_count
        FROM order_items
        GROUP BY item_name
        ORDER BY total_quantity DESC
        LIMIT 5
        """, conn
    )

    conn.close()

    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'avg_order': avg_order,
        'today_orders': today_orders,
        'today_revenue': today_revenue,
        'top_items': top_items
    }


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_menu_data():
    """Load menu data from JSON file"""
    try:
        with open(MENU_PATH, 'r', encoding='utf-8') as f:
            menu_data = json.load(f)
        return pd.DataFrame(menu_data)
    except FileNotFoundError:
        st.error(f"Menu file not found at: {MENU_PATH}")
        return pd.DataFrame()
    except json.JSONDecodeError:
        st.error(f"Invalid JSON in menu file")
        return pd.DataFrame()


def display_order_card(order_row):
    """Display a single order as a card"""
    with st.container():
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.markdown(f"**Order ID:** `{order_row['order_id']}`")
        with col2:
            st.markdown(f"**Customer:** {order_row['customer_name']}")
        with col3:
            st.markdown(f"**Total:** ${order_row['total_amount']:.2f}")

        col5, col6 = st.columns([3, 1])
        with col5:
            st.markdown(f"**Date:** {order_row['created_at']}")
        with col6:
            status_color = "green" if order_row['status'] == 'confirmed' else "orange"
            st.markdown(f"**Status:** :{status_color}[{order_row['status']}]")


# Main Dashboard
def main():
    # Header
    st.title("FoodJoint Order Dashboard")
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.header("Dashboard Controls")

        view_mode = st.radio(
            "Select View",
            ["Overview", "Search Orders", "All Orders", "Analytics", "Menu"],
            index=0
        )

        st.markdown("---")

        # Refresh button
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.caption(f"Database: `orders.db`")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Main content based on view mode
    if view_mode == "Overview":
        show_overview()
    elif view_mode == "Search Orders":
        show_search()
    elif view_mode == "All Orders":
        show_all_orders()
    elif view_mode == "Analytics":
        show_analytics()
    else:  # Menu
        show_menu()


def show_overview():
    """Display overview dashboard"""
    st.header("Overview")

    # Get statistics
    stats = get_statistics()

    # Display key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Orders", stats['total_orders'])
    with col2:
        st.metric("Total Revenue", f"${stats['total_revenue']:.2f}")
    with col3:
        st.metric("Avg Order Value", f"${stats['avg_order']:.2f}")
    with col4:
        st.metric("Today's Orders", stats['today_orders'])
    with col5:
        st.metric("Today's Revenue", f"${stats['today_revenue']:.2f}")

    st.markdown("---")

    # Recent orders
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Recent Orders")
        df = get_all_orders()

        if len(df) > 0:
            # Show last 10 orders
            for idx, row in df.head(10).iterrows():
                with st.expander(
                    f"{row['order_id']} - {row['customer_name']} - ${row['total_amount']:.2f}",
                    expanded=False
                ):
                    display_order_details_inline(row['order_id'])
        else:
            st.info("No orders yet.")

    with col2:
        st.subheader("Top Items")
        if len(stats['top_items']) > 0:
            for idx, row in stats['top_items'].iterrows():
                st.markdown(
                    f"**{idx + 1}. {row['item_name']}**\n"
                    f"- Sold: {row['total_quantity']} units\n"
                    f"- Orders: {row['order_count']}"
                )
                st.markdown("---")
        else:
            st.info("No items ordered yet.")


def show_search():
    """Display search interface"""
    st.header("Search Orders")

    # Search controls
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search_term = st.text_input(
            "Enter search term",
            placeholder="Type order ID or customer name...",
            key="search_input"
        )

    with col2:
        search_by = st.selectbox(
            "Search by",
            ["Order ID", "Customer Name"],
            key="search_type"
        )

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        search_button = st.button("Search", use_container_width=True)

    st.markdown("---")

    # Perform search
    if search_term or search_button:
        if search_term:
            with st.spinner("Searching..."):
                results = search_orders(search_term, search_by)

            if len(results) > 0:
                st.success(f"Found {len(results)} order(s)")

                # Display results
                for idx, row in results.iterrows():
                    with st.expander(
                        f"{row['order_id']} - {row['customer_name']} - ${row['total_amount']:.2f}",
                        expanded=(len(results) == 1)
                    ):
                        display_order_details_inline(row['order_id'])
            else:
                st.warning(f"No orders found for '{search_term}'")
        else:
            st.info("Please enter a search term")


def show_all_orders():
    """Display all orders in a table"""
    st.header("All Orders")

    df = get_all_orders()

    if len(df) > 0:
        # Filters
        col1, col2 = st.columns([1, 3])

        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=df['status'].unique().tolist(),
                default=df['status'].unique().tolist()
            )

        # Apply filters
        filtered_df = df[df['status'].isin(status_filter)]

        st.info(f"Showing {len(filtered_df)} of {len(df)} orders")

        # Display table
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "order_id": st.column_config.TextColumn("Order ID", width="medium"),
                "customer_name": st.column_config.TextColumn("Customer", width="medium"),
                "total_amount": st.column_config.NumberColumn(
                    "Total",
                    format="$%.2f",
                    width="small"
                ),
                "created_at": st.column_config.TextColumn("Date", width="medium"),
                "status": st.column_config.TextColumn("Status", width="small")
            }
        )

        # Select order to view details
        st.markdown("---")
        selected_order = st.selectbox(
            "Select an order to view details",
            options=filtered_df['order_id'].tolist(),
            key="order_select"
        )

        if selected_order:
            st.subheader(f"Order Details: {selected_order}")
            display_order_details_inline(selected_order)
    else:
        st.info("No orders in the database yet.")


def show_analytics():
    """Display analytics and insights"""
    st.header("Analytics & Insights")

    stats = get_statistics()

    # Summary metrics
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Orders", stats['total_orders'])
        st.metric("Today's Orders", stats['today_orders'])

    with col2:
        st.metric("Total Revenue", f"${stats['total_revenue']:.2f}")
        st.metric("Today's Revenue", f"${stats['today_revenue']:.2f}")

    with col3:
        st.metric("Average Order Value", f"${stats['avg_order']:.2f}")
        if stats['total_orders'] > 0:
            st.metric("Items per Order", f"{stats['total_orders']:.1f}")

    st.markdown("---")

    # Top items chart
    st.subheader("Top Selling Items")

    if len(stats['top_items']) > 0:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.bar_chart(
                stats['top_items'].set_index('item_name')['total_quantity'],
                use_container_width=True
            )

        with col2:
            st.dataframe(
                stats['top_items'],
                hide_index=True,
                column_config={
                    "item_name": "Item",
                    "total_quantity": "Quantity Sold",
                    "order_count": "# Orders"
                },
                use_container_width=True
            )
    else:
        st.info("No data available yet.")

    st.markdown("---")

    # Recent trends
    st.subheader("Recent Activity")

    conn = sqlite3.connect(str(DB_PATH))
    daily_orders = pd.read_sql_query(
        """
        SELECT date(created_at) as date,
               COUNT(*) as order_count,
               SUM(total_amount) as revenue
        FROM orders
        GROUP BY date(created_at)
        ORDER BY date DESC
        LIMIT 7
        """, conn
    )
    conn.close()

    if len(daily_orders) > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Orders per Day**")
            st.line_chart(
                daily_orders.set_index('date')['order_count'],
                use_container_width=True
            )

        with col2:
            st.markdown("**Revenue per Day**")
            st.line_chart(
                daily_orders.set_index('date')['revenue'],
                use_container_width=True
            )
    else:
        st.info("Not enough data to show trends yet.")


def show_menu():
    """Display menu in tabular form"""
    st.header("Menu")

    # Load menu data
    df = get_menu_data()

    if df.empty:
        st.warning("No menu data available.")
        return

    # Menu statistics
    st.subheader("Menu Statistics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Items", len(df))
    with col2:
        st.metric("Categories", df['category'].nunique())
    with col3:
        avg_price = df['price'].mean()
        st.metric("Avg Price", f"${avg_price:.2f}")
    with col4:
        price_range = f"${df['price'].min():.2f} - ${df['price'].max():.2f}"
        st.metric("Price Range", price_range)

    st.markdown("---")

    # Filters
    st.subheader("Filter Menu")
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        # Category filter
        categories = ["All"] + sorted(df['category'].unique().tolist())
        selected_category = st.selectbox(
            "Filter by Category",
            options=categories,
            key="category_filter"
        )

    with col2:
        # Price range filter
        min_price = float(df['price'].min())
        max_price = float(df['price'].max())
        price_range = st.slider(
            "Price Range ($)",
            min_value=min_price,
            max_value=max_price,
            value=(min_price, max_price),
            step=0.5,
            key="price_filter"
        )

    with col3:
        # Search by name
        search_term = st.text_input(
            "Search by Name",
            placeholder="Type item name...",
            key="menu_search"
        )

    # Apply filters
    filtered_df = df.copy()

    if selected_category != "All":
        filtered_df = filtered_df[filtered_df['category'] == selected_category]

    filtered_df = filtered_df[
        (filtered_df['price'] >= price_range[0]) &
        (filtered_df['price'] <= price_range[1])
    ]

    if search_term:
        filtered_df = filtered_df[
            filtered_df['name'].str.contains(search_term, case=False, na=False)
        ]

    st.info(f"Showing {len(filtered_df)} of {len(df)} items")

    st.markdown("---")

    # Display menu table
    st.subheader("Menu Items")

    if len(filtered_df) > 0:
        # Prepare display dataframe
        display_df = filtered_df[['name', 'category', 'price']].copy()
        display_df = display_df.sort_values(['category', 'name'])

        # Display table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn(
                    "Item Name",
                    width="large",
                    help="Name of the menu item"
                ),
                "category": st.column_config.TextColumn(
                    "Category",
                    width="medium",
                    help="Item category"
                ),
                "price": st.column_config.NumberColumn(
                    "Price",
                    format="$%.2f",
                    width="small",
                    help="Price in USD"
                )
            }
        )

        # Category breakdown
        st.markdown("---")
        st.subheader("Items by Category")

        category_counts = filtered_df['category'].value_counts().sort_index()
        col1, col2 = st.columns([2, 1])

        with col1:
            st.bar_chart(category_counts, use_container_width=True)

        with col2:
            for category, count in category_counts.items():
                avg_cat_price = filtered_df[filtered_df['category'] == category]['price'].mean()
                st.markdown(
                    f"**{category.title()}**\n"
                    f"- Items: {count}\n"
                    f"- Avg Price: ${avg_cat_price:.2f}"
                )
                st.markdown("---")
    else:
        st.warning("No items match your filters. Try adjusting the filters.")


def display_order_details_inline(order_id):
    """Display detailed order information"""
    order_df, items_df = get_order_details(order_id)

    if len(order_df) > 0:
        order = order_df.iloc[0]

        # Order info
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Order ID:** `{order['order_id']}`")
            st.markdown(f"**Customer Name:** {order['customer_name']}")

        with col2:
            st.markdown(f"**Order Date:** {order['created_at']}")
            st.markdown(f"**Status:** {order['status']}")
            st.markdown(f"**Total Amount:** ${order['total_amount']:.2f}")

        # Order items
        st.markdown("**Order Items:**")

        if len(items_df) > 0:
            for idx, item in items_df.iterrows():
                item_total = item['item_price'] * item['quantity']

                # Parse addons
                addons_str = ""
                if item['addons'] and item['addons'] != 'null':
                    try:
                        addons = json.loads(item['addons'])
                        if addons:
                            addons_str = f" ({', '.join(addons)})"
                    except:
                        pass

                st.markdown(
                    f"- **{item['quantity']}x {item['item_name']}{addons_str}** - "
                    f"${item['item_price']:.2f} each = ${item_total:.2f}"
                )
        else:
            st.info("No items in this order")


if __name__ == "__main__":
    # Check if database exists
    if not DB_PATH.exists():
        st.error(f"Database not found at: {DB_PATH}")
        st.info("Please run the agent first to create the database.")
    else:
        main()
