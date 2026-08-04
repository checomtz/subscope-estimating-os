import streamlit as st
import plotly.express as px
from utils import load_data

load_data()
st.title("Executive Dashboard")

proj = st.session_state.get("selected_project", "All")
f_bids = st.session_state.bids[st.session_state.bids["Project"] == proj] if proj != "All" else st.session_state.bids

if not f_bids.empty:
    k1, k2, k3 = st.columns(3)
    k1.metric("Active Bids", len(f_bids))
    k2.metric("Total Bid Value", f"${f_bids['Base Bid ($)'].sum():,.2f}")
    k3.metric("Accepted Contracts", len(f_bids[f_bids['Status'] == 'Accepted']))
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📈 Bid Spreads by Trade")
        st.plotly_chart(px.box(f_bids, x="Trade", y="Base Bid ($)", color="Trade", template="plotly_dark"), use_container_width=True)
    with c2:
        st.markdown("### 💰 Cost Distribution")
        st.plotly_chart(px.pie(f_bids, names="Trade", values="Base Bid ($)", hole=0.4, template="plotly_dark"), use_container_width=True)
else:
    st.info("No data available for this project.")