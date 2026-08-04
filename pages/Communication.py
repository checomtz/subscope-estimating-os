import streamlit as st
from utils import load_data

load_data()
st.title("Automated Follow-Up Engine")

proj = st.session_state.get("selected_project", "All")
f_bids = st.session_state.bids[st.session_state.bids["Project"] == proj] if proj != "All" else st.session_state.bids

if not f_bids.empty:
    col_sel, col_email = st.columns([1, 2])
    with col_sel:
        sub = st.selectbox("Subcontractor", options=f_bids["Subcontractor"].tolist())
    with col_email:
        row = f_bids[f_bids["Subcontractor"] == sub].iloc[0]
        body = f"Hello {row['Subcontractor']} Team,\n\nRegarding your {row['Trade']} quote of ${row['Base Bid ($)']:,.2f} for {row['Project']}...\n\nBest,\nSergio Calvillo\nMillis Development & Construction"
        st.text_area("Email Draft", value=body, height=250)
else:
    st.info("No bids available.")