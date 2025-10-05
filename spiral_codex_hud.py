#!/usr/bin/env python3
"""
Spiral Codex HUD - Exo Cluster Monitor

Universal monitoring dashboard for Exo local cluster and all AI providers.
Real-time status, health metrics, and manual control interface.
"""

import streamlit as st
import json
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from exo_integration import ExoTokenManagerIntegration, ExoReliakitProvider
    from exo_provider import ExoNodeStatus
except ImportError:
    st.error("Please ensure exo_integration.py and exo_provider.py are in the same directory")
    st.stop()


# Page configuration
st.set_page_config(
    page_title="Spiral Codex HUD - AI Command Bridge",
    page_icon="🌀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00ff00;
        text-align: center;
        text-shadow: 0 0 10px #00ff00;
        margin-bottom: 1rem;
    }
    .status-healthy {
        color: #00ff00;
        font-weight: bold;
    }
    .status-degraded {
        color: #ffaa00;
        font-weight: bold;
    }
    .status-offline {
        color: #ff0000;
        font-weight: bold;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
        border: 1px solid #00ff00;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .node-card {
        background: #1a1a1a;
        border-left: 4px solid #00ff00;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


class SpiralCodexHUD:
    """Universal HUD for AI provider monitoring and control"""
    
    def __init__(self):
        """Initialize HUD with session state"""
        if 'exo_integration' not in st.session_state:
            st.session_state.exo_integration = None
            st.session_state.auto_refresh = True
            st.session_state.refresh_interval = 5
            st.session_state.history = []
    
    def initialize_integration(self, host: str, port: int):
        """Initialize Exo integration"""
        try:
            st.session_state.exo_integration = ExoTokenManagerIntegration(
                exo_host=host,
                exo_port=port,
                enable_auto_failover=True
            )
            st.session_state.exo_integration.start()
            return True
        except Exception as e:
            st.error(f"Failed to initialize: {e}")
            return False
    
    def render_header(self):
        """Render main header"""
        st.markdown('<div class="main-header">🌀 SPIRAL CODEX HUD</div>', unsafe_allow_html=True)
        st.markdown("**AI Command Bridge** - Universal Provider Monitor & Control")
        st.markdown("---")
    
    def render_sidebar(self):
        """Render sidebar configuration"""
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # Connection settings
            st.subheader("Exo Cluster Connection")
            host = st.text_input("Host", value="localhost")
            port = st.number_input("Port", value=8000, min_value=1, max_value=65535)
            
            if st.button("🔌 Connect to Exo", type="primary"):
                if self.initialize_integration(host, port):
                    st.success("✅ Connected to Exo cluster")
                    st.rerun()
            
            st.markdown("---")
            
            # Auto-refresh settings
            st.subheader("Display Settings")
            st.session_state.auto_refresh = st.checkbox(
                "Auto-refresh",
                value=st.session_state.auto_refresh
            )
            st.session_state.refresh_interval = st.slider(
                "Refresh interval (seconds)",
                min_value=1,
                max_value=60,
                value=st.session_state.refresh_interval
            )
            
            st.markdown("---")
            
            # Manual controls
            st.subheader("Manual Controls")
            
            if st.button("🔄 Force Refresh"):
                st.rerun()
            
            if st.button("🧹 Clear History"):
                st.session_state.history = []
                st.rerun()
            
            if st.session_state.exo_integration:
                if st.button("🛑 Disconnect"):
                    st.session_state.exo_integration.stop()
                    st.session_state.exo_integration = None
                    st.rerun()
    
    def render_cluster_overview(self, status: Dict):
        """Render cluster overview cards"""
        exo = status.get("exo", {})
        health = exo.get("health", {})
        
        # Main status cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            is_available = exo.get("available", False)
            status_color = "🟢" if is_available else "🔴"
            st.metric(
                label=f"{status_color} Cluster Status",
                value="ONLINE" if is_available else "OFFLINE"
            )
        
        with col2:
            healthy = health.get("healthy_nodes", 0)
            total = health.get("total_nodes", 0)
            st.metric(
                label="🖥️ Active Nodes",
                value=f"{healthy}/{total}"
            )
        
        with col3:
            models = len(exo.get("available_models", []))
            st.metric(
                label="🤖 Available Models",
                value=models
            )
        
        with col4:
            cost = exo.get("cost", 0.0)
            st.metric(
                label="💰 Cost",
                value=f"${cost:.2f}",
                delta="Always FREE!"
            )
    
    def render_node_details(self, status: Dict):
        """Render detailed node information"""
        st.subheader("📡 Node Details")
        
        nodes = status.get("exo", {}).get("nodes", {})
        
        if not nodes:
            st.info("No nodes detected. Check your Exo cluster is running.")
            return
        
        for node_id, node_info in nodes.items():
            node_status = node_info.get("status", "offline")
            
            # Determine status color
            if node_status == "online":
                status_class = "status-healthy"
                status_icon = "🟢"
            elif node_status == "degraded":
                status_class = "status-degraded"
                status_icon = "🟡"
            else:
                status_class = "status-offline"
                status_icon = "🔴"
            
            with st.container():
                st.markdown(f"""
                <div class="node-card">
                    <h4>{status_icon} {node_info.get('device', 'Unknown Device')}</h4>
                    <p><strong>ID:</strong> {node_id}</p>
                    <p><strong>Status:</strong> <span class="{status_class}">{node_status.upper()}</span></p>
                    <p><strong>Memory:</strong> {node_info.get('memory_gb', 0):.1f} GB</p>
                    <p><strong>Models:</strong> {node_info.get('models', 0)}</p>
                    <p><strong>Last Seen:</strong> {node_info.get('last_seen', 'Never')}</p>
                </div>
                """, unsafe_allow_html=True)
    
    def render_usage_metrics(self, status: Dict):
        """Render usage statistics"""
        st.subheader("📊 Usage Metrics")
        
        usage = status.get("exo", {}).get("usage", {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            requests = usage.get("total_requests", 0)
            st.metric("Total Requests", requests)
        
        with col2:
            compute_time = usage.get("total_compute_time", 0)
            st.metric("Compute Time", f"{compute_time:.2f}s")
        
        with col3:
            avg_time = usage.get("avg_compute_time", 0)
            st.metric("Avg Response Time", f"{avg_time:.2f}s")
        
        # Request history chart
        if st.session_state.history:
            self.render_history_chart()
    
    def render_history_chart(self):
        """Render request history chart"""
        if len(st.session_state.history) < 2:
            return
        
        # Create time series chart
        timestamps = [h["timestamp"] for h in st.session_state.history]
        requests = [h["requests"] for h in st.session_state.history]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=requests,
            mode='lines+markers',
            name='Requests',
            line=dict(color='#00ff00', width=2)
        ))
        
        fig.update_layout(
            title="Request History",
            xaxis_title="Time",
            yaxis_title="Total Requests",
            template="plotly_dark",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_model_selector(self, status: Dict):
        """Render model selection interface"""
        st.subheader("🤖 Model Selection")
        
        models = status.get("exo", {}).get("available_models", [])
        
        if not models:
            st.warning("No models available. Start your Exo cluster with models.")
            return
        
        selected_model = st.selectbox(
            "Select Model",
            options=models,
            key="selected_model"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=0.7,
                step=0.1
            )
        
        with col2:
            max_tokens = st.number_input(
                "Max Tokens",
                min_value=1,
                max_value=4096,
                value=512
            )
        
        # Chat interface
        prompt = st.text_area("Prompt", height=100)
        
        if st.button("🚀 Send Request", type="primary"):
            if not st.session_state.exo_integration:
                st.error("Not connected to Exo cluster")
                return
            
            with st.spinner("Processing..."):
                messages = [{"role": "user", "content": prompt}]
                
                response, error, provider = st.session_state.exo_integration.route_request(
                    model=selected_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if error:
                    st.error(f"Error: {error}")
                else:
                    st.success(f"Response from {provider}")
                    
                    # Extract response content
                    if "choices" in response:
                        content = response["choices"][0].get("message", {}).get("content", "")
                        st.markdown("**Response:**")
                        st.code(content)
                    
                    # Show metadata
                    if "exo_metadata" in response:
                        meta = response["exo_metadata"]
                        st.info(f"⚡ Computed in {meta.get('compute_time', 0):.2f}s on {meta.get('device', 'unknown')}")
    
    def render_recommendation(self, status: Dict):
        """Render system recommendation"""
        recommendation = status.get("recommendation", "")
        
        if recommendation:
            if "✅" in recommendation:
                st.success(recommendation)
            elif "⚠️" in recommendation:
                st.warning(recommendation)
            elif "🔴" in recommendation:
                st.error(recommendation)
            else:
                st.info(recommendation)
    
    def update_history(self, status: Dict):
        """Update request history"""
        usage = status.get("exo", {}).get("usage", {})
        
        st.session_state.history.append({
            "timestamp": datetime.now(),
            "requests": usage.get("total_requests", 0),
            "compute_time": usage.get("total_compute_time", 0)
        })
        
        # Keep only last 100 entries
        if len(st.session_state.history) > 100:
            st.session_state.history = st.session_state.history[-100:]
    
    def render(self):
        """Main render loop"""
        self.render_header()
        self.render_sidebar()
        
        # Main content
        if not st.session_state.exo_integration:
            st.info("👈 Connect to your Exo cluster using the sidebar")
            
            # Quick start guide
            st.subheader("🚀 Quick Start")
            st.markdown("""
            1. Ensure your Exo cluster is running: `python3 ~/exo/main.py`
            2. Enter connection details in the sidebar (default: localhost:8000)
            3. Click **Connect to Exo**
            4. Monitor your cluster and send requests!
            """)
            return
        
        # Get status
        try:
            status = st.session_state.exo_integration.get_unified_status()
            self.update_history(status)
        except Exception as e:
            st.error(f"Failed to get status: {e}")
            return
        
        # Render components
        self.render_recommendation(status)
        st.markdown("---")
        
        self.render_cluster_overview(status)
        st.markdown("---")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            self.render_node_details(status)
        
        with col2:
            self.render_usage_metrics(status)
        
        st.markdown("---")
        self.render_model_selector(status)
        
        # Auto-refresh
        if st.session_state.auto_refresh:
            time.sleep(st.session_state.refresh_interval)
            st.rerun()


# Main execution
if __name__ == "__main__":
    hud = SpiralCodexHUD()
    hud.render()
