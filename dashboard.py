"""
SCADA System Web Dashboard
Real-time monitoring and control interface using Streamlit
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import json
from typing import Dict, List, Optional

# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"
REFRESH_INTERVAL = 2  # seconds

# Page configuration
st.set_page_config(
    page_title="SCADA Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Session State Management
# ============================================================================

if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "selected_node" not in st.session_state:
    st.session_state.selected_node = None

# ============================================================================
# API Helper Functions
# ============================================================================

def make_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make authenticated API request"""
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=5)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
    
    except Exception as e:
        return {"error": str(e)}

def login(username: str, password: str) -> bool:
    """Authenticate user"""
    response = make_request(
        "/api/auth/login",
        method="POST",
        data={"username": username, "password": password}
    )
    
    if "error" not in response and "token" in response:
        st.session_state.token = response["token"]
        st.session_state.username = response["username"]
        st.session_state.role = response["role"]
        return True
    
    return False

def logout():
    """Logout user"""
    if st.session_state.token:
        make_request("/api/auth/logout", method="POST")
    
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.role = None

# ============================================================================
# Login Page
# ============================================================================

def show_login_page():
    """Display login page"""
    st.title("🔒 SCADA System Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Authentication Required")
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("Login", use_container_width=True):
                if username and password:
                    if login(username, password):
                        st.success(f"Welcome, {username}!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                else:
                    st.warning("Please enter username and password")
        
        with col_b:
            if st.button("Clear", use_container_width=True):
                st.rerun()
        
        # Show default credentials
        st.markdown("---")
        st.markdown("**Default Credentials:**")
        st.code("""
admin / admin123 (Administrator)
operator / operator123 (Operator)
viewer / viewer123 (Viewer)
        """)

# ============================================================================
# Dashboard Components
# ============================================================================

def show_system_overview():
    """Display system overview panel"""
    st.header("📊 System Overview")
    
    # Get system overview data
    overview = make_request("/api/system/overview")
    
    if "error" in overview:
        st.error(f"Error loading system overview: {overview['error']}")
        return
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Nodes",
            overview.get("total_nodes", 0),
            delta=f"{overview.get('connected_nodes', 0)} connected"
        )
    
    with col2:
        st.metric(
            "Total Power",
            f"{overview.get('total_power_mw', 0):.1f} MW"
        )
    
    with col3:
        critical = overview.get("critical_alarms", 0)
        st.metric(
            "Critical Alarms",
            critical,
            delta="⚠️" if critical > 0 else "✅"
        )
    
    with col4:
        st.metric(
            "Total Alarms",
            overview.get("total_alarms", 0)
        )
    
    # Timestamp
    st.caption(f"Last updated: {overview.get('timestamp', 'N/A')}")

def show_node_list():
    """Display list of all nodes"""
    st.header("⚙️ Grid Nodes")
    
    nodes_data = make_request("/api/nodes")
    
    if "error" in nodes_data:
        st.error(f"Error loading nodes: {nodes_data['error']}")
        return
    
    nodes = nodes_data.get("nodes", [])
    
    if not nodes:
        st.info("No nodes available. Start the simulator first.")
        return
    
    # Create DataFrame
    df = pd.DataFrame(nodes)
    
    # Display as interactive table
    st.dataframe(
        df,
        column_config={
            "node_id": "Node ID",
            "ip_address": "IP Address",
            "protocols": st.column_config.ListColumn("Protocols"),
            "connected": st.column_config.CheckboxColumn("Connected")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Node selection
    node_ids = [n["node_id"] for n in nodes]
    selected = st.selectbox("Select node for details:", node_ids, key="node_selector")
    
    if selected:
        st.session_state.selected_node = selected

def show_node_details(node_id: str):
    """Display detailed node status"""
    st.header(f"🔍 Node Details: {node_id}")
    
    status = make_request(f"/api/nodes/{node_id}/status")
    
    if "error" in status:
        st.error(f"Error loading node status: {status['error']}")
        return
    
    # Display electrical measurements
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Voltage", f"{status.get('voltage_kv', 0):.2f} kV")
    
    with col2:
        st.metric("Current", f"{status.get('current_a', 0):.1f} A")
    
    with col3:
        st.metric("Power", f"{status.get('power_mw', 0):.2f} MW")
    
    with col4:
        st.metric("Frequency", f"{status.get('frequency_hz', 0):.3f} Hz")
    
    # Breaker status
    breaker_closed = status.get("breaker_closed", False)
    st.info(f"Breaker Status: {'🟢 CLOSED' if breaker_closed else '🔴 OPEN'}")
    
    # Control buttons (if authorized)
    st.subheader("Controls")
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        if st.button("Close Breaker", use_container_width=True):
            send_command(node_id, "close_breaker")
    
    with col_b:
        if st.button("Open Breaker", use_container_width=True):
            send_command(node_id, "open_breaker")
    
    with col_c:
        if st.button("Reset Alarms", use_container_width=True):
            send_command(node_id, "reset_alarms")
    
    # Node alarms
    alarms = status.get("alarms", [])
    if alarms:
        st.warning(f"⚠️ {len(alarms)} active alarm(s)")
        for alarm in alarms:
            st.error(f"**{alarm.get('alarm_type')}**: {alarm.get('description')} (Severity: {alarm.get('severity')})")

def send_command(node_id: str, action: str, value=None):
    """Send control command to node"""
    result = make_request(
        f"/api/nodes/{node_id}/command",
        method="POST",
        data={"node_id": node_id, "action": action, "value": value}
    )
    
    if "error" in result:
        st.error(f"Command failed: {result['error']}")
    else:
        st.success(f"Command '{action}' sent successfully!")
        time.sleep(1)
        st.rerun()

def show_alarms():
    """Display alarm management panel"""
    st.header("🚨 Alarm Management")
    
    # Filters
    col1, col2 = st.columns(2)
    
    with col1:
        severity_filter = st.selectbox(
            "Filter by Severity",
            ["All", "CRITICAL", "WARNING", "INFO"],
            key="alarm_severity_filter"
        )
    
    with col2:
        node_filter = st.text_input("Filter by Node ID", key="alarm_node_filter")
    
    # Build query parameters
    params = []
    if severity_filter != "All":
        params.append(f"severity={severity_filter}")
    if node_filter:
        params.append(f"node_id={node_filter}")
    
    query_string = "&".join(params)
    endpoint = f"/api/alarms?{query_string}" if query_string else "/api/alarms"
    
    # Get alarms
    alarms_data = make_request(endpoint)
    
    if "error" in alarms_data:
        st.error(f"Error loading alarms: {alarms_data['error']}")
        return
    
    alarms = alarms_data.get("alarms", [])
    
    if not alarms:
        st.success("✅ No active alarms")
        return
    
    # Display alarms
    st.info(f"Total alarms: {len(alarms)}")
    
    for i, alarm in enumerate(alarms):
        severity = alarm.get("severity", "INFO")
        color = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARNING" else "🔵"
        
        with st.expander(f"{color} {alarm.get('node_id')} - {alarm.get('alarm_type')}", expanded=(i < 3)):
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                st.write(f"**Severity:** {severity}")
            with col_b:
                st.write(f"**Value:** {alarm.get('value', 'N/A')}")
            with col_c:
                st.write(f"**Time:** {alarm.get('timestamp', 'N/A')}")
            
            st.write(f"**Description:** {alarm.get('description', 'N/A')}")

def show_historical_data():
    """Display historical data charts"""
    st.header("📈 Historical Data")
    
    # Node selection
    nodes_data = make_request("/api/nodes")
    if "error" in nodes_data:
        st.error("Error loading nodes")
        return
    
    node_ids = [n["node_id"] for n in nodes_data.get("nodes", [])]
    
    if not node_ids:
        st.info("No nodes available")
        return
    
    selected_node = st.selectbox("Select Node", node_ids, key="historical_node")
    
    # Time range selection
    col1, col2 = st.columns(2)
    
    with col1:
        hours_back = st.slider("Hours of history", 1, 24, 1)
    
    with col2:
        bucket_interval = st.selectbox(
            "Aggregation Interval",
            ["1 minute", "5 minutes", "15 minutes", "1 hour"],
            index=1
        )
    
    # Query historical data
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours_back)
    
    hist_data = make_request(
        "/api/historian/query",
        method="POST",
        data={
            "node_id": selected_node,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "bucket_interval": bucket_interval
        }
    )
    
    if "error" in hist_data:
        st.warning(f"No historical data available: {hist_data['error']}")
        return
    
    measurements = hist_data.get("measurements", [])
    
    if not measurements:
        st.info("No measurements found for this time range")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(measurements)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Plot voltage
    fig_voltage = go.Figure()
    fig_voltage.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["voltage_kv"],
        mode="lines",
        name="Voltage",
        line=dict(color="blue", width=2)
    ))
    fig_voltage.update_layout(
        title="Voltage Over Time",
        xaxis_title="Time",
        yaxis_title="Voltage (kV)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_voltage, use_container_width=True)
    
    # Plot power
    fig_power = go.Figure()
    fig_power.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["power_mw"],
        mode="lines",
        name="Power",
        line=dict(color="green", width=2),
        fill="tozeroy"
    ))
    fig_power.update_layout(
        title="Power Over Time",
        xaxis_title="Time",
        yaxis_title="Power (MW)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_power, use_container_width=True)
    
    # Plot frequency
    fig_freq = go.Figure()
    fig_freq.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["frequency_hz"],
        mode="lines",
        name="Frequency",
        line=dict(color="red", width=2)
    ))
    fig_freq.add_hline(y=60.0, line_dash="dash", line_color="gray", annotation_text="Nominal")
    fig_freq.update_layout(
        title="Frequency Over Time",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_freq, use_container_width=True)

def show_audit_log():
    """Display security audit log"""
    st.header("🔐 Security Audit Log")
    
    # Check if user has admin permissions
    if st.session_state.role not in ["ADMINISTRATOR", "SUPERVISOR"]:
        st.warning("⚠️ Admin permissions required to view audit log")
        return
    
    # Filters
    col1, col2 = st.columns(2)
    
    with col1:
        limit = st.number_input("Number of events", 10, 1000, 100, 10)
    
    with col2:
        event_type = st.selectbox(
            "Event Type",
            ["All", "LOGIN_SUCCESS", "LOGIN_FAILURE", "COMMAND_ISSUED", "ACCESS_DENIED"],
            key="audit_event_filter"
        )
    
    # Build query
    endpoint = f"/api/security/audit?limit={limit}"
    if event_type != "All":
        endpoint += f"&event_type={event_type}"
    
    # Get audit events
    audit_data = make_request(endpoint)
    
    if "error" in audit_data:
        st.error(f"Error loading audit log: {audit_data['error']}")
        return
    
    events = audit_data.get("events", [])
    
    if not events:
        st.info("No audit events found")
        return
    
    # Display events
    st.info(f"Showing {len(events)} events")
    
    # Convert to DataFrame
    df = pd.DataFrame(events)
    
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        height=400
    )

def show_statistics():
    """Display system statistics"""
    st.header("📊 System Statistics")
    
    # Get security statistics
    stats = make_request("/api/security/statistics")
    
    if "error" not in stats:
        st.subheader("Security Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Events", stats.get("total_events", 0))
        with col2:
            st.metric("Active Sessions", stats.get("active_sessions", 0))
        with col3:
            st.metric("Total Users", stats.get("total_users", 0))
        
        # Event breakdown
        if "events_by_type" in stats:
            st.subheader("Events by Type")
            event_df = pd.DataFrame(
                list(stats["events_by_type"].items()),
                columns=["Event Type", "Count"]
            )
            
            fig = px.bar(event_df, x="Event Type", y="Count", title="Audit Events Distribution")
            st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# Main Dashboard
# ============================================================================

def show_main_dashboard():
    """Display main dashboard"""
    
    # Sidebar
    with st.sidebar:
        st.title("⚡ SCADA Dashboard")
        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        st.markdown("---")
        
        # Navigation
        page = st.radio(
            "Navigation",
            [
                "📊 System Overview",
                "⚙️ Node List",
                "🔍 Node Details",
                "🚨 Alarms",
                "📈 Historical Data",
                "🔐 Audit Log",
                "📊 Statistics"
            ]
        )
        
        st.markdown("---")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        
        if auto_refresh:
            refresh_rate = st.slider("Refresh rate (seconds)", 1, 10, REFRESH_INTERVAL)
            st.caption(f"Next refresh in {refresh_rate}s")
        
        st.markdown("---")
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
    
    # Main content
    if page == "📊 System Overview":
        show_system_overview()
    
    elif page == "⚙️ Node List":
        show_node_list()
    
    elif page == "🔍 Node Details":
        if st.session_state.selected_node:
            show_node_details(st.session_state.selected_node)
        else:
            st.info("Please select a node from the Node List page")
    
    elif page == "🚨 Alarms":
        show_alarms()
    
    elif page == "📈 Historical Data":
        show_historical_data()
    
    elif page == "🔐 Audit Log":
        show_audit_log()
    
    elif page == "📊 Statistics":
        show_statistics()
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

# ============================================================================
# Application Entry Point
# ============================================================================

def main():
    """Main application entry point"""
    
    # Check API health
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=2).json()
        if health.get("status") != "healthy":
            st.error("⚠️ API server is not healthy. Please start the API server first.")
            st.code("python3 api_server.py")
            return
    except:
        st.error("❌ Cannot connect to API server. Please start the API server first.")
        st.code("python3 api_server.py")
        return
    
    # Show login or dashboard
    if not st.session_state.token:
        show_login_page()
    else:
        show_main_dashboard()

if __name__ == "__main__":
    main()
