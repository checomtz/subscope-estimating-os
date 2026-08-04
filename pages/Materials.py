import streamlit as st
import plotly.express as px
import pandas as pd
import io
from utils import (
    load_table,
    save_table,
    reconcile_takeoff_quantities,
    CSI_CODES
)

st.title("Material Management, Takeoffs & Roll-Ups")

mats_cols = [
    "Subcontractor", "Subcontractor ID", "Project", "Category", 
    "Material Description", "Quantity", "Unit", "Unit Price ($)", 
    "Total Price ($)", "Source Document"
]
mats_df = load_table("sub_materials", mats_cols)

bids_cols = [
    "Subcontractor", "Subcontractor ID", "Trade", "Project", "Base Bid ($)", 
    "Adjustment ($)", "Inclusions/Notes", "Rating", "Status", "Version", 
    "Timestamp", "Is_Active", "EMR", "COI_Valid", "Bonding_Limit_USD", 
    "Source Document", "Review_Notes", "Commercial_Exceptions"
]
bids_df = load_table("bids", bids_cols)

takeoffs_cols = ["Trade", "Scope / Material", "Project", "Quantity", "Unit", "Est. Unit Cost ($)"]
takeoffs_df = load_table("takeoffs", takeoffs_cols)

CHART_THEME = ["#0284C7", "#059669", "#D97706", "#4F46E5", "#0891B2", "#7C3AED", "#475569"]

if not mats_df.empty:
    hist_avg = mats_df.groupby(["Material Description", "Unit"])["Unit Price ($)"].mean().reset_index()
    hist_avg.rename(columns={"Unit Price ($)": "Historical Avg ($)"}, inplace=True)
    
    benchmarked_df = pd.merge(mats_df, hist_avg, on=["Material Description", "Unit"], how="left")
    benchmarked_df["Variance (%)"] = ((benchmarked_df["Unit Price ($)"] - benchmarked_df["Historical Avg ($)"]) / benchmarked_df["Historical Avg ($)"]) * 100
    benchmarked_df["Variance (%)"] = pd.to_numeric(benchmarked_df["Variance (%)"], errors="coerce").fillna(0.0)
    
    spikes = benchmarked_df[benchmarked_df["Variance (%)"] > 10.0]
    if not spikes.empty:
        st.warning(f"PRICE ALERT: {len(spikes)} material item(s) are bidding more than 10% above historical averages.")
        with st.expander("View Historical Price Alerts"):
            st.dataframe(
                spikes[["Subcontractor ID", "Material Description", "Unit", "Unit Price ($)", "Historical Avg ($)", "Source Document", "Variance (%)"]].style.format({
                    "Unit Price ($)": "${:,.2f}",
                    "Historical Avg ($)": "${:,.2f}",
                    "Variance (%)": "{:+.1f}%"
                }),
                use_container_width=True, hide_index=True
            )

t1, t2, t3 = st.tabs(["Database Editor & Subcontractor Totals", "Takeoff vs. Quoted Quantity Reconciliation", "Financial Roll-Up & Export"])

with t1:
    st.markdown("### Itemized Database Editor")
    display_mats = mats_df.drop(columns=["Subcontractor"], errors="ignore")
    cols = ["Subcontractor ID"] + [c for c in display_mats.columns if c != "Subcontractor ID"]
    display_mats = display_mats[cols]
    
    edited = st.data_editor(
        display_mats, 
        num_rows="dynamic", 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Subcontractor ID": st.column_config.TextColumn("Sub ID", disabled=True),
            "Category": st.column_config.SelectboxColumn("Category", options=["Material", "Labor / Service", "Equipment", "Allowance", "Alternate"]),
            "Quantity": st.column_config.NumberColumn("Quantity", format="%,.2f"),
            "Unit Price ($)": st.column_config.NumberColumn("Unit Price ($)", format="$ %,.2f"),
            "Total Price ($)": st.column_config.NumberColumn("Total Price ($)", format="$ %,.2f"),
            "Source Document": st.column_config.TextColumn("Source Document", disabled=True)
        }
    )
    
    if st.button("Save Database Changes", type="primary"):
        if "Subcontractor" not in edited.columns:
             name_map = bids_df.set_index("Subcontractor ID")["Subcontractor"].to_dict()
             edited["Subcontractor"] = edited["Subcontractor ID"].map(name_map)
        save_table("sub_materials", edited)
        st.success("SQLite database updated.")
        st.rerun()

with t2:
    st.markdown("### Internal Estimating Takeoff Benchmark Editor")
    current_takeoffs = takeoffs_df if not takeoffs_df.empty else pd.DataFrame([
        {"Trade": "03 00 00 - Concrete", "Scope / Material": "Foundation Slab Concrete", "Project": "Metro Commercial Center", "Quantity": 4200.0, "Unit": "CuYd", "Est. Unit Cost ($)": 135.0}
    ])
        
    edited_takeoffs = st.data_editor(
        current_takeoffs,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Trade": st.column_config.SelectboxColumn("CSI Trade Division", options=CSI_CODES, required=True),
            "Scope / Material": st.column_config.TextColumn("Scope / Material Description", required=True),
            "Quantity": st.column_config.NumberColumn("Takeoff Target Qty", format="%,.2f"),
            "Unit": st.column_config.SelectboxColumn("Unit", options=["SqFt", "LnFt", "CuYd", "SqYd", "Ea", "Hrs", "Ton", "Lbs", "Gal", "Lump Sum"], required=True),
            "Est. Unit Cost ($)": st.column_config.NumberColumn("Est. Unit Cost ($)", format="$ %,.2f")
        }
    )
    
    if st.button("Save Internal Takeoff Targets", type="primary"):
        save_table("takeoffs", edited_takeoffs)
        st.toast("Saved internal takeoff target benchmarks!")
        st.rerun()
        
    st.markdown("---")
    reconciled_df = reconcile_takeoff_quantities(
        mats_df=mats_df,
        takeoffs_df=edited_takeoffs,
        bids_df=bids_df
    )
    
    if not reconciled_df.empty:
        st.dataframe(
            reconciled_df.style.format({
                "Internal Takeoff Qty": "{:,.2f}",
                "Quoted Qty": "{:,.2f}",
                "Variance (%)": "{:+.1f}%",
                "Shortfall Exposure ($)": "${:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )

with t3:
    if not mats_df.empty:
        summary = mats_df.groupby(["Material Description", "Unit"]).agg({"Quantity": "sum", "Total Price ($)": "sum"}).reset_index()
        summary["Avg Unit Price ($)"] = summary["Total Price ($)"] / summary["Quantity"]
        c1, c2 = st.columns([2, 1])
        with c1:
            st.dataframe(summary.style.format({"Quantity": "{:,.2f}", "Avg Unit Price ($)": "${:,.2f}", "Total Price ($)": "${:,.2f}"}), use_container_width=True, hide_index=True)
        with c2:
            fig3 = px.pie(summary, names="Material Description", values="Total Price ($)", hole=0.5, color_discrete_sequence=CHART_THEME)
            st.plotly_chart(fig3, use_container_width=True)