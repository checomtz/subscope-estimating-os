import streamlit as st
import plotly.express as px
import pandas as pd
import utils
import io
import os
import streamlit.components.v1 as components
from utils import (
    init_db,
    load_table,
    save_table,
    extract_pdf_text,
    display_pdf,
    process_with_gemini,
    generate_sub_id,
    load_css,
    evaluate_scope_risk,
    generate_owner_gmp_pdf,
    reconcile_takeoff_quantities,
    generate_subcontract_loi_pdf,
    generate_leveling_matrix,
    process_takeoffs_with_gemini,
    CSI_CODES,
    SCOPE_GAP_TEMPLATES,
    DB_FILE
)
from datetime import datetime

# ----------------------------------------
# 1. Page Configuration & Design
# ----------------------------------------
st.set_page_config(
    page_title="SubScope | Estimating OS",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load external stylesheet
load_css("style.css")

CHART_THEME = ["#0284C7", "#059669", "#D97706", "#4F46E5", "#0891B2", "#7C3AED", "#475569"]

# Initialize SQLite database and load tables
init_db()

bids_cols = [
    "Subcontractor", "Subcontractor ID", "Trade", "Project", "Base Bid ($)", 
    "Adjustment ($)", "Inclusions/Notes", "Rating", "Status", "Version", 
    "Timestamp", "Is_Active", "EMR", "COI_Valid", "Bonding_Limit_USD", 
    "Source Document", "Review_Notes", "Commercial_Exceptions"
]
bids_df = load_table("bids", bids_cols)

mats_cols = [
    "Subcontractor", "Subcontractor ID", "Project", "Category", 
    "Material Description", "Quantity", "Unit", "Unit Price ($)", 
    "Total Price ($)", "Source Document"
]
mats_df = load_table("sub_materials", mats_cols)

takeoffs_cols = ["Trade", "Scope / Material", "Project", "Quantity", "Unit", "Est. Unit Cost ($)"]
takeoffs_df = load_table("takeoffs", takeoffs_cols)

targets_cols = ["Project", "Trade", "Target_Budget ($)", "Building_GSF"]
targets_df = load_table("targets", targets_cols)

# Ensure required columns
if "Adjustment ($)" not in bids_df.columns:
    bids_df["Adjustment ($)"] = 0.0
if "Is_Active" not in bids_df.columns:
    bids_df["Is_Active"] = 1
if "Source Document" not in bids_df.columns:
    bids_df["Source Document"] = "Manual Entry / Legacy PDF"
if "Review_Notes" not in bids_df.columns:
    bids_df["Review_Notes"] = ""
if "Commercial_Exceptions" not in bids_df.columns:
    bids_df["Commercial_Exceptions"] = ""

# ----------------------------------------
# 2. Executive Sidebar (Logo, Scope Filter & Reset Button)
# ----------------------------------------
sidebar_logo_html = """
<div class="logo-container">
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 21H21" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
        <path d="M5 21V7L13 3V21" stroke="#0284C7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M19 21V11L13 7" stroke="#0284C7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M9 9V9.01" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
        <path d="M9 13V13.01" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
        <path d="M9 17V17.01" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <span class="logo-title">SubScope</span>
</div>
"""
st.sidebar.markdown(sidebar_logo_html, unsafe_allow_html=True)
st.sidebar.caption("Commercial Estimating & Bid Leveling")
st.sidebar.markdown("---")

active_projects = bids_df[bids_df["Is_Active"] == 1]["Project"].dropna().unique().tolist() if not bids_df.empty else []
existing_projects = sorted(list(set(active_projects)))

selected_project = st.sidebar.selectbox("Active Project Scope", ["All"] + existing_projects)

active_bids = bids_df[bids_df["Is_Active"] == 1] if not bids_df.empty else bids_df
f_bids = active_bids[active_bids["Project"] == selected_project] if selected_project != "All" and not active_bids.empty else active_bids
f_mats = mats_df[mats_df["Project"] == selected_project] if selected_project != "All" and not mats_df.empty else mats_df
f_targets = targets_df[targets_df["Project"] == selected_project] if selected_project != "All" and not targets_df.empty else targets_df
f_takeoffs = takeoffs_df[takeoffs_df["Project"] == selected_project] if selected_project != "All" and not takeoffs_df.empty else takeoffs_df

st.sidebar.markdown("---")
with st.sidebar.expander("Database Reset & Controls"):
    st.caption("Wipe the SQLite project database to start testing from a clean, blank slate.")
    if st.button("Reset Database to Blank Slate", type="primary", use_container_width=True):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        st.toast("SQLite database cleared. Reloading as a blank slate!")
        st.rerun()

# ----------------------------------------
# 3. Top Horizontal Navigation Bar
# ----------------------------------------
page = st.radio(
    "Primary Navigation",
    [
        "Home / Overview",
        "Executive Dashboard", 
        "Quote Parsing & Entry", 
        "Analytics & Comparisons", 
        "Material Management", 
        "Team Communications"
    ],
    horizontal=True,
    label_visibility="collapsed"
)
st.markdown("---")

# ==========================================
# PAGE 0: HOME / LANDING PAGE
# ==========================================
if page == "Home / Overview":
    st.markdown("""
    <div class="splash-card">
        <div style="display: flex; justify-content: center; margin-bottom: 12px;">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 21H21" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
                <path d="M5 21V7L13 3V21" stroke="#0284C7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M19 21V11L13 7" stroke="#0284C7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M9 9V9.01" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
                <path d="M9 13V13.01" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
                <path d="M9 17V17.01" stroke="#0284C7" stroke-width="2" stroke-linecap="round"/>
            </svg>
        </div>
        <h1 style="font-size: 34px; margin-bottom: 8px;">SubScope Estimating Operating System</h1>
        <p style="font-size: 17px; color: #475569; max-width: 680px; margin: 0 auto 20px auto;">
            The enterprise preconstruction command center built for commercial contractors to parse proposals, level subcontractor bids, and automate project buyout.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Active Project Snapshot")
    total_active_bids = len(f_bids) if not f_bids.empty else 0
    total_val = float(f_bids["Base Bid ($)"].sum()) if not f_bids.empty else 0.0
    awarded_count = len(f_bids[f_bids["Status"] == "Accepted"]) if not f_bids.empty else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Subcontractor Quotes", f"{total_active_bids} Bids Logged")
    m2.metric("Total Quoted Scope Value", f"${total_val:,.2f}")
    m3.metric("Awarded Subcontracts", f"{awarded_count} Bids Accepted")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### How SubScope Works")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 01. AI Proposal Extraction")
        st.caption("Upload raw subcontractor PDF quotes to automatically extract CSI MasterFormat trade divisions, base bid amounts, and itemized materials in seconds.")
    with c2:
        st.markdown("#### 02. Bid Normalization & Leveling")
        st.caption("Apply financial scope-gap allowances and compare competing subcontractors head-to-head to eliminate hidden costs and exclusions.")
    with c3:
        st.markdown("#### 03. Buyout & Contract Execution")
        st.caption("Lock in accepted subcontracts, generate formal Letter of Intent (LOI) agreements, and export 4-Page Owner GMP Approval PDF Reports with one click.")

    st.markdown("---")
    st.markdown("### Core Preconstruction Modules")
    mod1, mod2 = st.columns(2)
    with mod1:
        st.markdown("**Executive Dashboard & Buyout**")
        st.caption("Track total projected project costs, apply financial leveling adjustments, generate formal Letter of Intent agreements, and download your Owner Approval PDF Report.")
        st.markdown("**Quote Parsing & Entry**")
        st.caption("Upload PDF vendor quotes, review visual AI extraction confidence scores, and assign standardized commercial units before saving to your matrix.")
    with mod2:
        st.markdown("**Analytics & Comparisons**")
        st.caption("Compare competing bidders side-by-side with automatic dollar spreads, compliance risk detection (EMR & COI), and interactive Subcontractor Rating & Review scorecards.")
        st.markdown("**Material Management & Takeoffs**")
        st.caption("Reconcile quoted quantities against internal estimating takeoffs, detect price spikes above historical averages, and audit itemized Schedules of Value.")

# ==========================================
# PAGE 1: EXECUTIVE DASHBOARD & BUYOUT
# ==========================================
elif page == "Executive Dashboard":
    st.title("Project Buyout & Executive Dashboard")
    
    if not f_bids.empty:
        f_bids = f_bids.copy()
        f_bids["Adjustment ($)"] = f_bids["Adjustment ($)"].fillna(0.0)
        f_bids["Normalized Bid ($)"] = f_bids["Base Bid ($)"] + f_bids["Adjustment ($)"]
        
        projected_cost = 0.0
        awarded_cost = 0.0
        proj_data = []
        
        trades = f_bids["Trade"].unique()
        for t in trades:
            t_bids = f_bids[f_bids["Trade"] == t]
            accepted = t_bids[t_bids["Status"] == "Accepted"]
            
            if not accepted.empty:
                val = float(accepted["Normalized Bid ($)"].sum())
                projected_cost += val
                awarded_cost += val
                proj_data.append({"Trade": t, "Subcontractor": accepted["Subcontractor"].iloc[0], "Cost": val, "Status": "Accepted (Locked)"})
            else:
                val = float(t_bids["Normalized Bid ($)"].min())
                projected_cost += val
                idx_min = t_bids["Normalized Bid ($)"].idxmin()
                sub = str(t_bids.loc[idx_min, "Subcontractor"]) + " (Estimate)"
                proj_data.append({"Trade": t, "Subcontractor": sub, "Cost": val, "Status": "Pending Lowest Bid"})
        
        proj_df = pd.DataFrame(proj_data)
        
        tot_target = float(f_targets["Target_Budget ($)"].sum()) if not f_targets.empty else 0.0
        buyout_diff = tot_target - projected_cost
        gsf_val = float(f_targets["Building_GSF"].iloc[0]) if not f_targets.empty and "Building_GSF" in f_targets.columns and pd.notna(f_targets["Building_GSF"].iloc[0]) else 25000.0
        cost_per_sf = projected_cost / gsf_val if gsf_val > 0 else 0.0
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Projected Project Cost", f"${projected_cost:,.2f}", f"${cost_per_sf:.2f} / SF")
        k2.metric("Total Awarded (Locked)", f"${awarded_cost:,.2f}")
        if tot_target > 0:
            k3.metric("Projected vs GMP Target", f"${tot_target:,.2f}", f"${buyout_diff:,.2f} Variance", delta_color="normal")
        else:
            k3.metric("Accepted Contracts", len(f_bids[f_bids['Status'] == 'Accepted']))
        
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Normalized Bid Spreads by Trade")
            fig = px.box(
                f_bids, x="Trade", y="Normalized Bid ($)", color="Trade",
                color_discrete_sequence=CHART_THEME
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
            fig.update_yaxes(gridcolor="#CBD5E1")
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("### Projected Cost Distribution")
            if not proj_df.empty:
                fig2 = px.pie(
                    proj_df, names="Trade", values="Cost", hole=0.45,
                    color_discrete_sequence=CHART_THEME,
                    hover_data=["Subcontractor", "Status"]
                )
                fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig2, use_container_width=True)
            
        st.markdown("---")
        with st.container(border=True):
            st.markdown("### Subcontractor Matrix & Apples-to-Apples Normalization")
            st.caption("Change a bidder's **Status** to `'Accepted'` to award them, or edit **Rating (1.0–5.0)** and **Adjustment ($)** directly in the table.")
            
            display_cols = ["Subcontractor ID", "Subcontractor", "Trade", "Base Bid ($)", "Adjustment ($)", "Normalized Bid ($)", "Rating", "Status", "Version"]
            
            edited_bids = st.data_editor(
                f_bids[display_cols],
                use_container_width=True,
                hide_index=True,
                disabled=["Subcontractor ID", "Subcontractor", "Trade", "Project", "Base Bid ($)", "Normalized Bid ($)", "Inclusions/Notes", "Source Document", "Version"],
                column_config={
                    "Base Bid ($)": st.column_config.NumberColumn("Base Bid", format="$ %,.2f"),
                    "Adjustment ($)": st.column_config.NumberColumn("Adjustment", format="$ %,.2f", step=500.0),
                    "Normalized Bid ($)": st.column_config.NumberColumn("Normalized Bid", format="$ %,.2f"),
                    "Rating": st.column_config.NumberColumn("Rating", format="⭐ %.1f", min_value=1.0, max_value=5.0, step=0.1),
                    "Status": st.column_config.SelectboxColumn("Status", options=["Submitted", "Under Review", "Accepted", "Rejected"]),
                    "Version": st.column_config.NumberColumn("Ver.", format="v%d")
                }
            )
            
            if not edited_bids[["Adjustment ($)", "Status", "Rating"]].equals(f_bids[["Adjustment ($)", "Status", "Rating"]]):
                for idx, row in edited_bids.iterrows():
                    match_idx = bids_df[
                        (bids_df["Subcontractor ID"] == row["Subcontractor ID"]) & 
                        (bids_df["Version"] == row["Version"])
                    ].index
                    if len(match_idx) > 0:
                        bids_df.loc[match_idx, "Adjustment ($)"] = row["Adjustment ($)"]
                        bids_df.loc[match_idx, "Status"] = row["Status"]
                        bids_df.loc[match_idx, "Rating"] = row["Rating"]
                save_table("bids", bids_df)
                st.rerun()

        st.markdown("---")
        with st.container(border=True):
            st.markdown("### AI Predictive Scope-Gap & Change Order Risk Engine")
            st.caption(f"Audits quotes using **Dollar-Weighted Completeness (%)** and **GSF-Scaled Change Order Exposure ($)** (assessed at **{gsf_val:,.0f} GSF**).")
            
            risk_data = []
            for _, row in f_bids.iterrows():
                eval_res = evaluate_scope_risk(
                    trade=row["Trade"],
                    sub_id=row["Subcontractor ID"],
                    base_bid=float(row.get("Base Bid ($)", 0.0) or 0.0),
                    building_gsf=gsf_val,
                    mats_df=f_mats,
                    inclusions_text=str(row.get("Inclusions/Notes", ""))
                )
                risk_data.append({
                    "Subcontractor ID": row["Subcontractor ID"],
                    "Subcontractor": row["Subcontractor"],
                    "Trade": row["Trade"],
                    "Completeness (%)": eval_res["score"],
                    "Risk Level": eval_res["risk_level"],
                    "Unstated Exclusions / Missing Scope": ", ".join(eval_res["missing"]) if eval_res["missing"] else "Complete Turnkey Scope",
                    "Est. Change Order Exposure ($)": eval_res["exposure"]
                })
                
            risk_df = pd.DataFrame(risk_data)
            st.dataframe(
                risk_df.style.format({
                    "Completeness (%)": "{:.1f}%",
                    "Est. Change Order Exposure ($)": "${:,.2f}"
                }).map(
                    lambda v: "color: #DC2626; font-weight: 700;" if v == "High Risk" else ("color: #D97706; font-weight: 600;" if v == "Moderate Risk" else "color: #059669; font-weight: 600;"),
                    subset=["Risk Level"]
                ),
                use_container_width=True,
                hide_index=True
            )
            
            with st.expander("One-Click RFI Scope Clarification Generator (Draft Audit Emails)"):
                st.caption("Generate an instant pre-award clarification email for subcontractors flagged with missing scope requirements.")
                c_rfi1, c_rfi2 = st.columns([1, 2])
                with c_rfi1:
                    rfi_sub_name = st.selectbox("Select Bidder for RFI Audit", options=risk_df["Subcontractor"].tolist(), key="rfi_sub_sel")
                    rfi_row = risk_df[risk_df["Subcontractor"] == rfi_sub_name].iloc[0]
                with c_rfi2:
                    missing_str = rfi_row["Unstated Exclusions / Missing Scope"]
                    if missing_str != "Complete Turnkey Scope" and rfi_row["Est. Change Order Exposure ($)"] > 0:
                        rfi_body = (
                            f"Subject: Scope Clarification RFI — {rfi_row['Trade']} Proposal ({rfi_row['Subcontractor']})\n\n"
                            f"Hello {rfi_row['Subcontractor']} Estimating Team,\n\n"
                            f"We are currently reviewing and leveling your proposal for {selected_project if selected_project != 'All' else 'the project'}. "
                            f"During our automated scope-gap audit, we noticed that the following standard trade requirements were not explicitly identified "
                            f"in your Schedule of Values or inclusions:\n\n"
                            f"  • {missing_str.replace(', ', '/n  • ')}\n\n"
                            f"Could you please confirm if these items are included in your base proposal price, or provide your itemized cost adders "
                            f"if they are currently excluded?\n\n"
                            f"Thank you,\nPreconstruction Department\nNorthstar Development Group"
                        )
                        st.text_area("Audit RFI Email Draft", value=rfi_body, height=220)
                    else:
                        st.success(f"{rfi_row['Subcontractor']}'s proposal covers all standard required trade scope items. No clarification RFI needed!")

            with st.expander("Delete Proposal / Quote from Database"):
                st.caption("Permanently remove a quote and all of its extracted material line items from the active project.")
                del_col1, del_col2 = st.columns([2, 1])
                with del_col1:
                    bid_options = f_bids.apply(
                        lambda r: f"[{r['Subcontractor ID']}] {r['Subcontractor']} — ${float(r['Base Bid ($)' ] or 0.0):,.2f} ({r.get('Source Document', 'Manual')})",
                        axis=1
                    ).tolist()
                    selected_bid_to_delete = st.selectbox("Select Quote to Permanently Remove", options=bid_options, key="del_quote_select")
                with del_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Delete Selected Quote", type="primary", use_container_width=True):
                        selected_idx = bid_options.index(selected_bid_to_delete)
                        row_to_del = f_bids.iloc[selected_idx]
                        target_sub_id = row_to_del["Subcontractor ID"]
                        target_source = row_to_del.get("Source Document", "Manual Entry / Legacy PDF")
                        target_proj = row_to_del["Project"]
                        
                        bids_keep_mask = ~(
                            (bids_df["Subcontractor ID"] == target_sub_id) &
                            (bids_df["Project"] == target_proj) &
                            (bids_df["Source Document"] == target_source) &
                            (bids_df["Is_Active"] == 1)
                        )
                        updated_bids = bids_df[bids_keep_mask].reset_index(drop=True)
                        save_table("bids", updated_bids)
                        
                        mats_keep_mask = ~(
                            (mats_df["Subcontractor ID"] == target_sub_id) &
                            (mats_df["Project"] == target_proj) &
                            (mats_df["Source Document"] == target_source)
                        )
                        updated_mats = mats_df[mats_keep_mask].reset_index(drop=True)
                        save_table("sub_materials", updated_mats)
                        
                        st.toast(f"Deleted quote for {row_to_del['Subcontractor']} and removed its material items.")
                        st.rerun()

            with st.expander("Scope-Gap Leveling Checklist Drawer (Automated Adjustments)"):
                st.caption("Select a bidder and apply standard trade-specific allowances to normalize incomplete proposals.")
                gap_col1, gap_col2 = st.columns([1, 2])
                with gap_col1:
                    selected_sub_gap_name = st.selectbox("Select Bidder to Level", options=f_bids["Subcontractor"].tolist())
                    selected_sub_gap_id = f_bids[f_bids["Subcontractor"] == selected_sub_gap_name]["Subcontractor ID"].iloc[0]
                    sub_trade = f_bids[f_bids["Subcontractor"] == selected_sub_gap_name]["Trade"].iloc[0]
                with gap_col2:
                    available_gaps = SCOPE_GAP_TEMPLATES.get(sub_trade, [])
                    if available_gaps:
                        total_allowance = 0.0
                        selected_items = []
                        for gap in available_gaps:
                            checked = st.checkbox(f"Add {gap['item']} (+${gap['default_cost']:,.2f})", key=f"gap_{selected_sub_gap_id}_{gap['item']}")
                            if checked:
                                total_allowance += gap["default_cost"]
                                selected_items.append(gap["item"])
                        
                        if st.button("Apply Leveling Adjustments to Selected Quote", type="primary"):
                            idx = bids_df[
                                (bids_df["Subcontractor ID"] == selected_sub_gap_id) & 
                                (bids_df["Is_Active"] == 1)
                            ].index
                            if len(idx) > 0:
                                first_idx = idx[0]
                                bids_df.loc[idx, "Adjustment ($)"] = total_allowance
                                
                                existing_notes = str(bids_df.at[first_idx, "Inclusions/Notes"] or "")
                                new_notes = existing_notes + f" | Leveling Additions: {', '.join(selected_items)}" if selected_items else existing_notes
                                
                                bids_df.loc[idx, "Inclusions/Notes"] = new_notes
                                save_table("bids", bids_df)
                                st.toast(f"Applied ${total_allowance:,.2f} leveling adjustment.")
                                st.rerun()
                    else:
                        st.info("No pre-configured scope-gap checklist items available for this CSI Division.")

        st.markdown("---")
        with st.container(border=True):
            st.markdown("### Owner GMP Approval Package Generator")
            st.caption("Compile your leveled buyout numbers, awarded subcontractor Schedule of Values, and compliance risk audit into an executive 4-Page PDF report.")
            
            gmp_col_info, gmp_col_dl = st.columns([2.5, 1])
            with gmp_col_info:
                st.markdown("""
                **Included Pages in Formal Owner PDF Report:**
                * **Page 01 — Executive Cover & GMP:** Total Project Value, Building GSF, Net GMP Target Variance, and Cost per SF.
                * **Page 02 — Trade Buyout & Leveling:** Complete trade-by-trade breakdown of selected/lowest subs, leveling allowances, and buyout status.
                * **Page 03 — Awarded Schedule of Values:** Full itemized line-item schedule for accepted subcontractors grouped by Category.
                * **Page 04 — Scope Audit & Compliance Cert.:** Safety EMR, Certificate of Insurance status, Completeness %, Risk Level, and Change Order Exposure.
                """)
            with gmp_col_dl:
                st.markdown("<br>", unsafe_allow_html=True)
                proj_label = selected_project if selected_project != "All" else "Metro Commercial Center"
                gmp_pdf_bytes = generate_owner_gmp_pdf(
                    bids_df=f_bids, 
                    mats_df=f_mats, 
                    targets_df=f_targets, 
                    project_name=proj_label, 
                    gsf_val=gsf_val
                )
                st.download_button(
                    label="Download Formal Owner GMP Approval Package (.pdf)",
                    data=gmp_pdf_bytes,
                    file_name=f"{proj_label.replace(' ', '_')}_Owner_GMP_Approval_Package.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

        st.markdown("---")
        with st.container(border=True):
            st.markdown("### One-Click Letter of Intent (LOI) & Subcontract Agreement Generator")
            st.caption("Generate a formal, ready-to-sign PDF Letter of Intent and Exhibit A Schedule of Values agreement for any subcontractor.")
            
            selected_loi_row = None
            sub_loi_mats = pd.DataFrame()
            loi_sub_names = f_bids["Subcontractor"].tolist() if not f_bids.empty else []

            loi_c1, loi_c2 = st.columns([2, 1])
            with loi_c1:
                if loi_sub_names:
                    selected_loi_sub = st.selectbox("Select Subcontractor for Formal Agreement Award", options=loi_sub_names, key="loi_sub_selector")
                    # Explicitly type-annotate as pd.DataFrame so Pylance does not get confused by pandas-stubs overloads
                    loi_matches: pd.DataFrame = f_bids[f_bids["Subcontractor"] == str(selected_loi_sub)]
                    if not loi_matches.empty:
                        selected_loi_row = loi_matches.iloc[0]
                        selected_loi_id = str(selected_loi_row["Subcontractor ID"])
                        sub_loi_mats = f_mats[f_mats["Subcontractor ID"] == selected_loi_id] if not f_mats.empty else pd.DataFrame()
                else:
                    st.info("No active bidders available to generate an LOI agreement.")
            with loi_c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if loi_sub_names and selected_loi_row is not None:
                    loi_pdf_bytes = generate_subcontract_loi_pdf(
                        sub_row=selected_loi_row,
                        sub_mats_df=sub_loi_mats,
                        project_name=selected_project if selected_project != "All" else "Metro Commercial Center"
                    )
                    st.download_button(
                        label="Download Subcontract LOI & Exhibit A (.pdf)",
                        data=loi_pdf_bytes,
                        file_name=f"Subcontract_LOI_Agreement_{str(selected_loi_row['Subcontractor']).replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )

        st.markdown("---")
        with st.container(border=True):
            st.markdown("### Awarded Subcontractor Roster & Category Buyout")
            awarded_df = f_bids[f_bids["Status"] == "Accepted"]
            
            if not awarded_df.empty:
                st.markdown("#### 01. Accepted Subcontracts")
                st.dataframe(
                    awarded_df[["Subcontractor ID", "Subcontractor", "Trade", "Normalized Bid ($)", "Source Document"]].style.format({"Normalized Bid ($)": "${:,.2f}"}),
                    use_container_width=True, 
                    hide_index=True
                )
                
                awarded_ids = awarded_df["Subcontractor ID"].tolist()
                itemized_awarded = f_mats[f_mats["Subcontractor ID"].isin(awarded_ids)].copy()
                
                if not itemized_awarded.empty:
                    if "Category" not in itemized_awarded.columns:
                        itemized_awarded["Category"] = "Material"
                    else:
                        itemized_awarded["Category"] = itemized_awarded["Category"].fillna("Material")
                        
                    trade_lookup = awarded_df.set_index("Subcontractor ID")["Trade"].to_dict()
                    itemized_awarded["Trade"] = itemized_awarded["Subcontractor ID"].map(trade_lookup)
                    
                    cat_summary = itemized_awarded.groupby("Category")["Total Price ($)"].sum().reset_index()
                    total_awarded_val = float(itemized_awarded["Total Price ($)"].sum())
                    cat_summary["% of Awarded Total"] = (cat_summary["Total Price ($)"] / total_awarded_val * 100) if total_awarded_val > 0 else 0.0
                    cat_summary.rename(columns={"Total Price ($)": "Category Total ($)"}, inplace=True)
                    
                    st.markdown("#### 02. Awarded Quotes by Cost Category")
                    c_cat_table, c_cat_chart = st.columns([1.5, 1])
                    with c_cat_table:
                        st.dataframe(
                            cat_summary.style.format({
                                "Category Total ($)": "${:,.2f}",
                                "% of Awarded Total": "{:.1f}%"
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                    with c_cat_chart:
                        fig_cat = px.pie(
                            cat_summary, names="Category", values="Category Total ($)", hole=0.5,
                            color_discrete_sequence=CHART_THEME
                        )
                        fig_cat.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10, b=10, l=10, r=10))
                        st.plotly_chart(fig_cat, use_container_width=True)
                    
                    # Executive-ready columns (strip internal IDs and source filenames for readability)
                    clean_cols = [
                        "Trade", "Subcontractor", "Category", 
                        "Material Description", "Quantity", "Unit", 
                        "Unit Price ($)", "Total Price ($)"
                    ]
                    export_df = itemized_awarded[[c for c in clean_cols if c in itemized_awarded.columns]].copy()
                    
                    # Rename column for professional presentation
                    export_df.rename(columns={"Material Description": "Scope / Item Description"}, inplace=True)
                    
                    # Round numbers cleanly so CSV/Excel opens without floating decimals
                    for num_col in ["Quantity", "Unit Price ($)", "Total Price ($)"]:
                        if num_col in export_df.columns:
                            export_df[num_col] = pd.to_numeric(export_df[num_col], errors="coerce").fillna(0.0).round(2)
                            
                    # Sort logically by Trade then Subcontractor
                    export_df.sort_values(by=["Trade", "Subcontractor", "Category"], inplace=True)
                    
                    col_dl1, col_dl2, col_dl3 = st.columns(3)
                    with col_dl1:
                        csv_items = export_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download Accepted Quotes (CSV)",
                            data=csv_items,
                            file_name="Accepted_Bids_Itemized_Quotes.csv",
                            mime="text/csv",
                            type="primary",
                            use_container_width=True
                        )
                    with col_dl2:
                        # Clean formatting for category totals export
                        clean_cats = cat_summary.copy()
                        clean_cats["Category Total ($)"] = clean_cats["Category Total ($)"].round(2)
                        clean_cats["% of Awarded Total"] = clean_cats["% of Awarded Total"].round(1)
                        csv_cats = clean_cats.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download Category Totals (CSV)",
                            data=csv_cats,
                            file_name="Accepted_Bids_Category_Totals.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    with col_dl3:
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            export_df.to_excel(writer, index=False, sheet_name='Itemized Quotes')
                            cat_summary.to_excel(writer, index=False, sheet_name='Category Totals')
                        st.download_button(
                            label="Download Combined Package (Excel)",
                            data=buf.getvalue(),
                            file_name="Accepted_Bids_Buyout_Package.xlsx",
                            mime="application/vnd.ms-excel",
                            use_container_width=True
                        )
                else:
                    st.info("No individual material/service line items found for the accepted bids yet.")
            else:
                st.info("No subcontractors have been awarded yet. Change a bidder's Status to 'Accepted' in the matrix above to build your final project roster.")
            
    else:
        st.info("The project database is currently empty. Navigate to **Quote Parsing & Entry** to upload your first proposal PDF!")

# ==========================================
# PAGE 2: QUOTE ENTRY
# ==========================================
elif page == "Quote Parsing & Entry":
    st.title("Quote Parsing & Entry")
    col1, col2 = st.columns([1, 1.2], gap="large")
    
    with col1:
        st.markdown("### Document Upload")
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            try:
                api_key = st.secrets.get("GEMINI_API_KEY", "")
            except Exception:
                api_key = ""
        uploaded_pdf = st.file_uploader("Upload Proposal PDF", type=["pdf"])
        if uploaded_pdf:
            display_pdf(uploaded_pdf)
            
    with col2:
        st.markdown("### AI Extraction & Verification")
        extracted_data = {"sub_name": "", "trade": CSI_CODES[0], "bid_amount": 0.0, "notes": "", "commercial_exceptions": [], "line_items": []}
        
        if uploaded_pdf and api_key and st.button("Run AI Extraction", type="primary", use_container_width=True):
            with st.spinner("Analyzing document visual structure, legal clauses, and line items..."):
                
                # Create the requirement text for the AI (Moved inside the button!)
                requirements_list = ""
                if not takeoffs_df.empty:
                    for _, row in takeoffs_df.iterrows():
                        requirements_list += f"- Need {row['Quantity']} {row['Unit']} of {row['Scope / Material']} for {row['Trade']}\n"

                res = process_with_gemini(uploaded_pdf, api_key, required_materials_text=requirements_list)
                if res:
                    st.session_state.temp_ai = res
                    st.success("Extraction complete.")
                    
        if "temp_ai" in st.session_state:
            extracted_data = st.session_state.temp_ai
            
            conf = extracted_data.get("confidence_score", 1.0)
            conf_color = "#059669" if conf >= 0.85 else "#D97706"
            st.markdown(f"""
            <div style="background: #FFFFFF; border: 1px solid #CBD5E1; border-left: 4px solid {conf_color}; padding: 12px 16px; border-radius: 6px; margin-bottom: 15px;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748B;">AI Confidence Score: <span style="color: {conf_color};">{conf * 100:.0f}%</span></div>
                <div style="font-size: 12px; color: #334155; margin-top: 4px;"><strong>Audit Reasoning:</strong> {extracted_data.get('extraction_scratchpad', 'Standard extraction completed.')}</div>
            </div>
            """, unsafe_allow_html=True)
            
            exceptions = extracted_data.get("commercial_exceptions", [])
            if exceptions:
                exc_list = "<br/>".join([f"• {x}" for x in exceptions])
                st.markdown(f"""
                <div style="background: #FEF2F2; border: 1px solid #FECACA; border-left: 4px solid #DC2626; padding: 12px 16px; border-radius: 6px; margin-bottom: 15px;">
                    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #991B1B;">⚠️ COMMERCIAL EXCEPTIONS / LEGAL LANDMINES DETECTED</div>
                    <div style="font-size: 12px; color: #7F1D1D; margin-top: 4px;">{exc_list}</div>
                </div>
                """, unsafe_allow_html=True)

        with st.form("verify_form", clear_on_submit=True):
            sub_name = st.text_input("Subcontractor Name", value=extracted_data.get("sub_name", ""))
            
            det_trade = extracted_data.get("trade", CSI_CODES[0])
            trade = st.selectbox("CSI Division Code", CSI_CODES, index=CSI_CODES.index(det_trade) if det_trade in CSI_CODES else 0)
            
            proj = st.text_input("Project", value=selected_project if selected_project != "All" else "Metro Commercial Center")
            bid_amt = st.number_input("Base Bid ($)", value=float(extracted_data.get("bid_amount", 0.0) or 0.0), step=500.0)
            notes = st.text_area("Scope / Inclusions", value=extracted_data.get("notes", ""))
            
            exc_str_val = "; ".join(extracted_data.get("commercial_exceptions", []))
            comm_exceptions = st.text_area("Commercial Exceptions / Legal Footnotes", value=exc_str_val)
            
            edited_line_items = []
            raw_items = extracted_data.get("line_items", [])
            if raw_items:
                st.markdown("#### Extracted Materials & Services Quoted")
                st.caption("Review and adjust categorized line items before committing to the project database.")
                
                items_df = pd.DataFrame(raw_items)
                required_cols = ["description", "category", "quantity", "unit", "unit_price", "total_price", "included_in_base"]
                for c in required_cols:
                    if c not in items_df.columns:
                        items_df[c] = ""
                
                display_items_df = items_df[required_cols].copy()
                display_items_df.columns = ["Description", "Category", "Qty", "Unit", "Unit Price ($)", "Total Price ($)", "In Base Bid"]
                
                edited_df = st.data_editor(
                    display_items_df,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "Category": st.column_config.SelectboxColumn(
                            "Category",
                            options=["Material", "Labor / Service", "Equipment", "Allowance", "Alternate"]
                        ),
                        "Qty": st.column_config.NumberColumn("Qty", format="%,.2f"),
                        "Unit": st.column_config.SelectboxColumn(
                            "Unit",
                            options=["SqFt", "LnFt", "CuYd", "SqYd", "Ea", "Hrs", "Ton", "Lbs", "Gal", "Lump Sum"],
                            required=True
                        ),
                        "Unit Price ($)": st.column_config.NumberColumn("Unit Price", format="$ %,.2f"),
                        "Total Price ($)": st.column_config.NumberColumn("Total Price", format="$ %,.2f"),
                        "In Base Bid": st.column_config.CheckboxColumn("In Base Bid")
                    }
                )
                edited_line_items = edited_df.to_dict("records")
            
            if st.form_submit_button("Save to Matrix", use_container_width=True):
                if sub_name:
                    sub_id = generate_sub_id(sub_name or "")
                    
                    existing_bids = bids_df[
                        (bids_df["Subcontractor ID"] == sub_id) & 
                        (bids_df["Project"] == proj)
                    ] if not bids_df.empty else pd.DataFrame()
                    
                    new_version = 1
                    if not existing_bids.empty:
                        bids_df.loc[existing_bids.index, "Is_Active"] = 0
                        new_version = int(existing_bids["Version"].max() + 1)
                        st.toast(f"Archived previous bid. Saving as Version {new_version}.")

                    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    src_file_label = uploaded_pdf.name if uploaded_pdf else "Manual Entry"
                    
                    new_row = pd.DataFrame([{
                        "Subcontractor": sub_name, "Subcontractor ID": sub_id, "Trade": trade, "Project": proj, 
                        "Base Bid ($)": bid_amt, "Adjustment ($)": 0.0, "Inclusions/Notes": notes, 
                        "Rating": 4.0, "Status": "Submitted", "Version": new_version, 
                        "Timestamp": now, "Is_Active": 1,
                        "EMR": 0.88, "COI_Valid": 1, "Bonding_Limit_USD": 2500000.0,
                        "Source Document": src_file_label, "Review_Notes": "",
                        "Commercial_Exceptions": comm_exceptions
                    }])
                    
                    updated_bids = pd.concat([bids_df, new_row], ignore_index=True)
                    save_table("bids", updated_bids)
                    
                    items_to_save = edited_line_items if edited_line_items else raw_items
                    if items_to_save:
                        mat_rows = []
                        for idx, i in enumerate(items_to_save):
                            desc = i.get("Description") or i.get("description", f"Line Item {idx+1}")
                            cat = i.get("Category") or i.get("category", "Material")
                            qty = float(i.get("Qty") or i.get("quantity", 1.0) or 1.0)
                            unit = i.get("Unit") or i.get("unit", "Lump Sum")
                            u_price = float(i.get("Unit Price ($)") or i.get("unit_price", 0.0) or 0.0)
                            t_price = float(i.get("Total Price ($)") or i.get("total_price", 0.0) or 0.0)
                            in_base = bool(i.get("In Base Bid", i.get("included_in_base", True)))
                            
                            mat_rows.append({
                                "Subcontractor": sub_name,
                                "Subcontractor ID": sub_id,
                                "Project": proj,
                                "Category": cat,
                                "Material Description": f"[{cat}] {desc}" if not in_base else desc,
                                "Quantity": qty,
                                "Unit": unit,
                                "Unit Price ($)": u_price,
                                "Total Price ($)": t_price,
                                "Source Document": src_file_label
                            })
                            
                        updated_mats = pd.concat([pd.DataFrame(mat_rows), mats_df], ignore_index=True)
                        save_table("sub_materials", updated_mats)
                    
                    if "temp_ai" in st.session_state: 
                        del st.session_state.temp_ai
                    st.toast("Saved successfully.")
                    st.rerun()
                    
        with st.expander("View Proposal History & Audit Trail"):
            hist_bids = bids_df[bids_df["Is_Active"] == 0] if not bids_df.empty else pd.DataFrame()
            if not hist_bids.empty:
                st.dataframe(
                    hist_bids[["Subcontractor ID", "Project", "Version", "Base Bid ($)", "Source Document", "Timestamp"]].sort_values("Timestamp", ascending=False),
                    use_container_width=True, hide_index=True
                )
            else:
                st.caption("No archived proposals found.")

# ==========================================
# PAGE 3: ANALYTICS & COMPARISONS
# ==========================================
elif page == "Analytics & Comparisons":
    st.title("Analytics & Bid Comparisons")
    
    tab1, tab2, tab3 = st.tabs(["Head-to-Head Matchup", "Subcontractor Scorecards & Reviews", "Side-by-Side Leveling Matrix"])
    
    with tab1:
        if len(f_bids) < 2:
            st.warning("You need at least two bids in the active project scope to run a side-by-side comparison.")
        else:
            avail_trades = sorted(list(set(f_bids["Trade"].dropna())))
            selected_trade = st.selectbox("Filter by CSI Division Code", options=avail_trades)
            trade_bids = f_bids[f_bids["Trade"] == selected_trade]
            
            if len(trade_bids) < 2:
                st.info(f"Only one active bid exists for {selected_trade}. Please select a trade with multiple competitors.")
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    sub_a_name = st.selectbox("Select Bidder A", options=trade_bids["Subcontractor"].tolist(), key="cmp_a")
                    sub_a_id = trade_bids[trade_bids["Subcontractor"] == sub_a_name]["Subcontractor ID"].iloc[0]
                with col_b:
                    other_subs = [s for s in trade_bids["Subcontractor"].tolist() if s != sub_a_name]
                    sub_b_name = st.selectbox("Select Bidder B", options=other_subs if other_subs else trade_bids["Subcontractor"].tolist(), key="cmp_b")
                    sub_b_id = trade_bids[trade_bids["Subcontractor"] == sub_b_name]["Subcontractor ID"].iloc[0]
                    
                st.markdown("---")
                
                data_a = trade_bids[trade_bids["Subcontractor ID"] == sub_a_id].iloc[0]
                data_b = trade_bids[trade_bids["Subcontractor ID"] == sub_b_id].iloc[0]
                
                base_a_val = float(data_a["Base Bid ($)"] or 0.0)
                base_b_val = float(data_b["Base Bid ($)"] or 0.0)
                diff_dollars = base_b_val - base_a_val
                diff_pct = (diff_dollars / base_a_val) * 100 if base_a_val > 0 else 0.0
                
                emr_a = float(data_a.get("EMR", 0.88) or 0.88)
                coi_a = bool(data_a.get("COI_Valid", 1))
                emr_b = float(data_b.get("EMR", 0.88) or 0.88)
                coi_b = bool(data_b.get("COI_Valid", 1))
                
                if emr_a > 1.0 or not coi_a or emr_b > 1.0 or not coi_b:
                    st.markdown("""
                    <div style="background: #FEF2F2; border: 1px solid #FECACA; border-left: 4px solid #DC2626; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
                        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #991B1B;">COMPLIANCE RISK DETECTED</div>
                        <div style="font-size: 13px; color: #7F1D1D; margin-top: 4px;">One or more selected subcontractors exceed standard corporate safety risk thresholds (EMR &gt; 1.0) or have an expired Certificate of Insurance on file.</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                m1, m2, m3 = st.columns(3)
                m1.metric(label=f"[{sub_a_id}] {sub_a_name} (v{data_a.get('Version', 1)})", value=f"${base_a_val:,.2f}")
                m2.metric(label=f"[{sub_b_id}] {sub_b_name} (v{data_b.get('Version', 1)})", value=f"${base_b_val:,.2f}", delta=f"${diff_dollars:,.2f} ({diff_pct:+.1f}%)", delta_color="inverse")
                m3.metric(label="Spread", value=f"${abs(diff_dollars):,.2f}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"#### {sub_a_name} Scope & Notes")
                    st.info(data_a.get("Inclusions/Notes", "No notes listed.") or "No notes listed.")
                    st.caption(f"Status: **{data_a['Status']}** | Rating: **⭐ {data_a['Rating']:.1f} / 5.0** | Source File: **{data_a.get('Source Document', 'N/A')}**")
                    
                    mats_a = f_mats[f_mats["Subcontractor ID"] == sub_a_id]
                    if not mats_a.empty:
                        st.markdown("**Extracted Material & Service Line Items**")
                        st.dataframe(
                            mats_a[["Material Description", "Quantity", "Unit", "Unit Price ($)", "Total Price ($)", "Source Document"]].style.format({
                                "Quantity": "{:,.2f}", "Unit Price ($)": "${:,.2f}", "Total Price ($)": "${:,.2f}"
                            }),
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.caption("No individual material items extracted for this bidder.")
                        
                with c2:
                    st.markdown(f"#### {sub_b_name} Scope & Notes")
                    st.info(data_b.get("Inclusions/Notes", "No notes listed.") or "No notes listed.")
                    st.caption(f"Status: **{data_b['Status']}** | Rating: **⭐ {data_b['Rating']:.1f} / 5.0** | Source File: **{data_b.get('Source Document', 'N/A')}**")
                    
                    mats_b = f_mats[f_mats["Subcontractor ID"] == sub_b_id]
                    if not mats_b.empty:
                        st.markdown("**Extracted Material & Service Line Items**")
                        st.dataframe(
                            mats_b[["Material Description", "Quantity", "Unit", "Unit Price ($)", "Total Price ($)", "Source Document"]].style.format({
                                "Quantity": "{:,.2f}", "Unit Price ($)": "${:,.2f}", "Total Price ($)": "${:,.2f}"
                            }),
                            use_container_width=True, hide_index=True
                        )
                    else:
                        st.caption("No individual material items extracted for this bidder.")

    with tab2:
        all_bids = bids_df
        if not all_bids.empty:
            sub_stats = all_bids.groupby(["Subcontractor ID", "Subcontractor"]).agg(
                Total_Bids=("Project", "nunique"),
                Projects_Won=("Status", lambda x: (x == "Accepted").sum()),
                Avg_Rating=("Rating", "mean")
            ).reset_index()
            sub_stats["Win_Rate (%)"] = (sub_stats["Projects_Won"] / sub_stats["Total_Bids"]) * 100
            
            c1, c2 = st.columns([1, 2])
            with c1:
                selected_sub_name = st.selectbox("Select Subcontractor to Review", options=sub_stats["Subcontractor"].tolist())
                sub_data = sub_stats[sub_stats["Subcontractor"] == selected_sub_name].iloc[0]
                selected_sub_id = sub_data["Subcontractor ID"]
                st.markdown(f"### [{selected_sub_id}] {selected_sub_name}")
                st.metric("Overall Average Rating", f"⭐ {sub_data['Avg_Rating']:.1f} / 5.0")
                st.metric("Win Rate", f"{sub_data['Win_Rate (%)']:.1f}%", f"{sub_data['Projects_Won']} Won / {sub_data['Total_Bids']} Bid")
                
            with c2:
                st.markdown("#### Historical Project Performance")
                history = all_bids[all_bids["Subcontractor ID"] == selected_sub_id][["Project", "Trade", "Base Bid ($)", "Rating", "Status", "Source Document", "Timestamp"]]
                def highlight_history(val):
                    if val == 'Accepted': return 'color: #059669; font-weight: 600;'
                    elif val == 'Rejected': return 'color: #DC2626;'
                    return ''
                st.dataframe(history.style.map(highlight_history, subset=['Status']).format({"Base Bid ($)": "${:,.2f}", "Rating": "⭐ {:.1f}"}), use_container_width=True, hide_index=True)
                
                st.markdown("#### Market Win-Rate Comparison")
                fig = px.bar(sub_stats.sort_values("Win_Rate (%)", ascending=False), x="Subcontractor", y="Win_Rate (%)", color="Avg_Rating", color_continuous_scale="Viridis")
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown(f"### Submit Field Evaluation & Review for {selected_sub_name}")
            st.caption("Rate vendor performance across key operational criteria and record qualitative field notes for future project teams.")
            
            with st.form("sub_review_form", clear_on_submit=True):
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    new_rating = st.slider("Overall Performance Score (1.0 = Poor, 5.0 = Exceptional)", min_value=1.0, max_value=5.0, value=4.0, step=0.1)
                    safety_rating = st.select_slider("Safety & EMR Compliance", options=["Unsatisfactory", "Fair", "Standard / Compliant", "Exceptional"])
                with r_col2:
                    quality_rating = st.select_slider("Workmanship & Quality", options=["Unsatisfactory", "Fair", "Good", "Turnkey Excellence"])
                    schedule_rating = st.select_slider("Schedule & Punctuality", options=["Delayed Schedule", "Minor Delays", "On Time", "Ahead of Schedule"])
                
                review_comments = st.text_area("Field Review Notes / Estimating Feedback", placeholder="e.g., Excellent craftsmanship on formwork; required minor follow-up for final site washdown.")
                
                if st.form_submit_button("Submit & Save Review", type="primary", use_container_width=True):
                    idx_to_update = bids_df[bids_df["Subcontractor ID"] == selected_sub_id].index
                    if len(idx_to_update) > 0:
                        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        bids_df.loc[idx_to_update, "Rating"] = new_rating
                        
                        full_note = f"[{now_str}] Score: {new_rating}/5.0 | Safety: {safety_rating} | Quality: {quality_rating} | Schedule: {schedule_rating} | Notes: {review_comments}"
                        
                        # Use the first matching row label with .at to get a clean Python scalar string
                        target_idx = idx_to_update[0]
                        existing_val = bids_df.at[target_idx, "Review_Notes"]
                        existing_notes = str(existing_val).strip() if pd.notna(existing_val) else ""
                        
                        updated_notes = f"{existing_notes}\n{full_note}" if existing_notes else full_note
                        bids_df.loc[idx_to_update, "Review_Notes"] = updated_notes
                        
                        save_table("bids", bids_df)
                        st.toast(f"Saved review for {selected_sub_name}! Updated average rating to ⭐ {new_rating:.1f}.")
                        st.rerun()

            st.markdown("#### Past Review Logs & Field Notes")
            sub_notes = all_bids[all_bids["Subcontractor ID"] == selected_sub_id]["Review_Notes"].dropna().unique().tolist()
            clean_notes = [n for n in sub_notes if str(n).strip()]
            if clean_notes:
                for note in clean_notes:
                    st.info(note)
            else:
                st.caption("No qualitative review notes recorded for this subcontractor yet.")
        else:
            st.info("No data available to generate scorecards.")

    with tab3:
        st.markdown("### Side-by-Side Bid Leveling Pivot Table")
        st.caption("Pivots extracted line-item schedules across all competing subcontractors for a single CSI Division.")
        
        avail_trades = sorted(list(set(f_bids["Trade"].dropna())))
        if not avail_trades:
            st.info("No trades found in active project scope.")
        else:
            selected_pivot_trade = st.selectbox("Select Trade to Pivot", options=avail_trades, key="pivot_trade")
            
            # Use str(selected_pivot_trade or "") so Pylance knows it is strictly a str and never None
            pivot_matrix = generate_leveling_matrix(
                mats_df=f_mats, 
                bids_df=f_bids, 
                trade=str(selected_pivot_trade or "")
            )
            
            if not pivot_matrix.empty:
                st.dataframe(
                    pivot_matrix.style.format({col: "${:,.2f}" for col in pivot_matrix.columns if col != "Material Description"}),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No itemized material/service rows found to build pivot table.")

# ==========================================
# PAGE 4: MATERIALS & TAKEOFFS
# ==========================================
elif page == "Material Management":
    st.title("Material Management, Takeoffs & Roll-Ups")
    
    all_mats = mats_df
    if not all_mats.empty and not f_mats.empty:
        hist_avg = all_mats.groupby(["Material Description", "Unit"])["Unit Price ($)"].mean().reset_index()
        hist_avg.rename(columns={"Unit Price ($)": "Historical Avg ($)"}, inplace=True)
        
        benchmarked_df = pd.merge(f_mats, hist_avg, on=["Material Description", "Unit"], how="left")
        benchmarked_df["Variance (%)"] = ((benchmarked_df["Unit Price ($)"] - benchmarked_df["Historical Avg ($)"]) / benchmarked_df["Historical Avg ($)"]) * 100
        benchmarked_df["Variance (%)"] = pd.to_numeric(benchmarked_df["Variance (%)"], errors="coerce").fillna(0.0)
        
        spikes = benchmarked_df[benchmarked_df["Variance (%)"] > 10.0]
        if not spikes.empty:
            st.warning(f"PRICE ALERT: {len(spikes)} material item(s) in this project scope are bidding more than 10% above your historical averages.")
            with st.expander("View Historical Price Alerts"):
                st.dataframe(
                    spikes[["Subcontractor ID", "Material Description", "Unit", "Unit Price ($)", "Historical Avg ($)", "Source Document", "Variance (%)"]].style.format({
                        "Unit Price ($)": "${:,.2f}",
                        "Historical Avg ($)": "${:,.2f}",
                        "Variance (%)": "{:+.1f}%"
                    }).map(lambda x: "color: #DC2626; font-weight: 600;" if pd.notna(x) and isinstance(x, (int, float)) and x > 10 else "", subset=["Variance (%)"]),
                    use_container_width=True, hide_index=True
                )
    
    t1, t2, t3 = st.tabs(["Database Editor & Subcontractor Totals", "Takeoff vs. Quoted Quantity Reconciliation", "Financial Roll-Up & Export"])
    
    with t1:
        st.markdown("### Itemized Database Editor")
        
        with st.expander("Delete Individual Material / Service Line Item(s)"):
            st.caption("Select specific material or service rows to permanently remove from the active project scope.")
            if not f_mats.empty:
                del_mat_col1, del_mat_col2 = st.columns([3, 1])
                with del_mat_col1:
                    mats_options = [
                        f"{idx} | [{row['Subcontractor ID']}] {row['Material Description']} — ${row['Total Price ($)']:,.2f} ({row.get('Source Document', 'Manual')})"
                        for idx, row in f_mats.iterrows()
                    ]
                    selected_mats_to_delete = st.multiselect("Select Line Item(s) to Remove", options=mats_options, key="del_mats_select")
                with del_mat_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Delete Selected Line Item(s)", type="primary", use_container_width=True):
                        if selected_mats_to_delete:
                            indices_to_drop = [int(sel.split(" | ")[0]) for sel in selected_mats_to_delete]
                            updated_mats = mats_df.drop(index=indices_to_drop).reset_index(drop=True)
                            save_table("sub_materials", updated_mats)
                            st.toast(f"Deleted {len(indices_to_drop)} line item(s) from SQLite database.")
                            st.rerun()
                        else:
                            st.warning("Please select at least one item from the dropdown.")
            else:
                st.info("No material line items available to delete.")

        display_mats = f_mats.drop(columns=["Subcontractor"], errors="ignore")
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
            if selected_project != "All":
                other = mats_df[mats_df["Project"] != selected_project]
                if "Subcontractor" not in edited.columns:
                     name_map = bids_df.set_index("Subcontractor ID")["Subcontractor"].to_dict()
                     edited["Subcontractor"] = edited["Subcontractor ID"].map(name_map)
                updated_mats = pd.concat([other, edited], ignore_index=True)
            else:
                 if "Subcontractor" not in edited.columns:
                     name_map = bids_df.set_index("Subcontractor ID")["Subcontractor"].to_dict()
                     edited["Subcontractor"] = edited["Subcontractor ID"].map(name_map)
                 updated_mats = edited
            
            save_table("sub_materials", updated_mats)
            st.success("SQLite database updated.")
            st.rerun()

        st.markdown("---")
        
        st.markdown("### Subcontractor Financial Summary & Variance Check")
        st.caption("Automatically calculates total itemized value per subcontractor and compares against their submitted Base Bid.")
        if not f_mats.empty and not f_bids.empty:
            sub_totals = f_mats.groupby(["Subcontractor ID", "Source Document"])["Total Price ($)"].sum().reset_index()
            sub_totals.rename(columns={"Total Price ($)": "Itemized Schedule Total ($)"}, inplace=True)
            
            bids_lookup = f_bids[["Subcontractor ID", "Subcontractor", "Base Bid ($)", "Trade"]].drop_duplicates(subset=["Subcontractor ID"])
            sub_summary = pd.merge(sub_totals, bids_lookup, on="Subcontractor ID", how="left")
            
            sub_summary["Base Bid ($)"] = pd.to_numeric(sub_summary["Base Bid ($)"], errors="coerce").fillna(0.0)
            sub_summary["Itemized Schedule Total ($)"] = pd.to_numeric(sub_summary["Itemized Schedule Total ($)"], errors="coerce").fillna(0.0)
            sub_summary["Variance ($)"] = sub_summary["Base Bid ($)"] - sub_summary["Itemized Schedule Total ($)"]
            
            st.dataframe(
                sub_summary[["Subcontractor ID", "Subcontractor", "Trade", "Source Document", "Itemized Schedule Total ($)", "Base Bid ($)", "Variance ($)"]].style.format({
                    "Itemized Schedule Total ($)": "${:,.2f}",
                    "Base Bid ($)": "${:,.2f}",
                    "Variance ($)": "${:,.2f}"
                }).map(
                    lambda v: "color: #DC2626; font-weight: 700;" if isinstance(v, (int, float)) and abs(v) > 50 else "color: #059669; font-weight: 600;", 
                    subset=["Variance ($)"]
                ),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No materials or bids available to generate subcontractor roll-up summaries.")

    with t2:
        st.markdown("### 📋 Internal Estimating Takeoff Benchmark Editor")
        st.caption("Enter your preconstruction estimating takeoff quantities below. The engine will automatically compare bidder quantities against these targets.")
        
        proj_label_takeoffs = selected_project if selected_project != "All" else "Metro Commercial Center"
        
        with st.expander("🤖 AI Takeoff Import (Upload Bill of Materials PDF)", expanded=False):
            takeoff_pdf = st.file_uploader("Upload your Engineer's Takeoff or Bill of Materials", type=["pdf"], key="takeoff_pdf")
            if takeoff_pdf and st.button("Extract Requirements from Document", type="primary"):
                api_key = os.environ.get("GEMINI_API_KEY", "") or st.secrets.get("GEMINI_API_KEY", "")
                with st.spinner("Extracting required materials..."):
                    res = process_takeoffs_with_gemini(takeoff_pdf, api_key)
                    if res and "items" in res:
                        new_rows = []
                        for item in res["items"]:
                            new_rows.append({
                                "Trade": item.get("trade", CSI_CODES[0]),
                                "Scope / Material": item.get("description", "Unknown Material"),
                                "Project": proj_label_takeoffs,
                                "Quantity": item.get("quantity", 1.0),
                                "Unit": item.get("unit", "Lump Sum"),
                                "Est. Unit Cost ($)": item.get("unit_cost", 0.0)
                            })
                        if new_rows:
                            updated_takeoffs = pd.concat([takeoffs_df, pd.DataFrame(new_rows)], ignore_index=True)
                            save_table("takeoffs", updated_takeoffs)
                            st.toast(f"Successfully imported {len(new_rows)} requirements!")
                            st.rerun()
                    else:
                        st.error("Could not extract items from this document.")

        current_takeoffs = takeoffs_df[takeoffs_df["Project"] == proj_label_takeoffs] if not takeoffs_df.empty else pd.DataFrame()
        if current_takeoffs.empty:
            current_takeoffs = pd.DataFrame([
                {"Trade": "03 00 00 - Concrete", "Scope / Material": "Foundation Slab Concrete", "Project": proj_label_takeoffs, "Quantity": 4200.0, "Unit": "CuYd", "Est. Unit Cost ($)": 135.0},
                {"Trade": "04 00 00 - Masonry", "Scope / Material": "CMU Block Exterior Wall", "Project": proj_label_takeoffs, "Quantity": 18500.0, "Unit": "SqFt", "Est. Unit Cost ($)": 14.0}
            ])
            
        edited_takeoffs = st.data_editor(
            current_takeoffs,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Trade": st.column_config.SelectboxColumn("CSI Trade Division", options=CSI_CODES, required=True),
                "Scope / Material": st.column_config.TextColumn("Scope / Material Description", required=True),
                "Project": st.column_config.TextColumn("Project", disabled=True),
                "Quantity": st.column_config.NumberColumn("Takeoff Target Qty", format="%,.2f"),
                "Unit": st.column_config.SelectboxColumn("Unit", options=["SqFt", "LnFt", "CuYd", "SqYd", "Ea", "Hrs", "Ton", "Lbs", "Gal", "Lump Sum"], required=True),
                "Est. Unit Cost ($)": st.column_config.NumberColumn("Est. Unit Cost ($)", format="$ %,.2f")
            }
        )
        
        if st.button("Save Internal Takeoff Targets", type="primary", key="save_takeoffs_btn"):
            edited_takeoffs["Project"] = proj_label_takeoffs
            other_proj_takeoffs = takeoffs_df[takeoffs_df["Project"] != proj_label_takeoffs] if not takeoffs_df.empty else pd.DataFrame()
            updated_takeoffs = pd.concat([other_proj_takeoffs, edited_takeoffs], ignore_index=True)
            save_table("takeoffs", updated_takeoffs)
            st.toast("Saved internal takeoff target benchmarks!")
            st.rerun()
            
        st.markdown("---")
        st.markdown("### Quantity Under-Scope Reconciliation Engine")
        st.caption("Flags subcontractors quoting more than **10% below internal takeoff volumes** and calculates financial shortfall exposure.")
        
        reconciled_df = reconcile_takeoff_quantities(
            mats_df=f_mats,
            takeoffs_df=edited_takeoffs,
            bids_df=f_bids
        )
        
        if not reconciled_df.empty:
            st.dataframe(
                reconciled_df.style.format({
                    "Internal Takeoff Qty": "{:,.2f}",
                    "Quoted Qty": "{:,.2f}",
                    "Variance (%)": "{:+.1f}%",
                    "Shortfall Exposure ($)": "${:,.2f}"
                }).map(
                    lambda v: "color: #DC2626; font-weight: 700;" if "Under-Scoped" in str(v) else ("color: #0284C7; font-weight: 600;" if "Over-Scoped" in str(v) else "color: #059669; font-weight: 600;"),
                    subset=["Risk Status"]
                ),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No quantity reconciliation data available. Ensure active bidders and takeoff target benchmarks share matching CSI Division Trade codes and Units.")

    with t3:
        if not f_mats.empty:
            summary = f_mats.groupby(["Material Description", "Unit"]).agg({"Quantity": "sum", "Total Price ($)": "sum"}).reset_index()
            
            # Clean up calculation and round to 2 decimal places for readable spreadsheets
            summary["Avg Unit Price ($)"] = (summary["Total Price ($)"] / summary["Quantity"]).round(2)
            summary["Quantity"] = summary["Quantity"].round(2)
            summary["Total Price ($)"] = summary["Total Price ($)"].round(2)
            
            # Rename columns to be executive-ready
            summary.rename(columns={"Material Description": "Scope / Item Description"}, inplace=True)
            summary = summary[["Scope / Item Description", "Quantity", "Unit", "Avg Unit Price ($)", "Total Price ($)"]]
            summary.sort_values(by="Total Price ($)", ascending=False, inplace=True)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.dataframe(
                    summary.style.format({
                        "Quantity": "{:,.2f}", 
                        "Avg Unit Price ($)": "${:,.2f}", 
                        "Total Price ($)": "${:,.2f}"
                    }), 
                    use_container_width=True, 
                    hide_index=True
                )
            with c2:
                fig3 = px.pie(summary, names="Scope / Item Description", values="Total Price ($)", hole=0.5, color_discrete_sequence=CHART_THEME)
                fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig3, use_container_width=True)
                
                # Add side-by-side CSV and Excel downloads with clean formatting
                dl_c1, dl_c2 = st.columns(2)
                with dl_c1:
                    csv_summary = summary.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Download Roll-Up (CSV)", 
                        data=csv_summary, 
                        file_name="Material_RollUp_Report.csv", 
                        mime="text/csv", 
                        use_container_width=True, 
                        type="primary"
                    )
                with dl_c2:
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        summary.to_excel(writer, index=False, sheet_name='Roll-Up')
                    st.download_button(
                        "Download Excel Report", 
                        data=buf.getvalue(), 
                        file_name="Material_Report.xlsx", 
                        mime="application/vnd.ms-excel", 
                        use_container_width=True
                    )
        else:
            st.info("No materials found in active project scope.")

# ==========================================
# PAGE 5: COMMUNICATIONS
# ==========================================
elif page == "Team Communications":
    st.title("Automated Follow-Up Engine")
    if not f_bids.empty:
        col_sel, col_email = st.columns([1, 2])
        with col_sel:
            sub = st.selectbox("Subcontractor", options=f_bids["Subcontractor"].tolist())
        with col_email:
            row = f_bids[f_bids["Subcontractor"] == sub].iloc[0]
            body = f"Hello {row['Subcontractor']} Team,\n\nRegarding your {row['Trade']} quote of ${float(row['Base Bid ($)' ] or 0.0):,.2f} for the {row['Project']} development...\n\nBest Regards,\nEstimating Department\nNorthstar Development Group"
            st.text_area("Email Draft", value=body, height=200)
            
            if os.path.exists("email_template.html"):
                if st.button("Preview HTML Email Template"):
                    with open("email_template.html", "r", encoding="utf-8") as f:
                        html_email = f.read()
                    html_email = html_email.replace("{{ sub_name }}", str(row['Subcontractor']))
                    html_email = html_email.replace("{{ project_name }}", str(row['Project']))
                    html_email = html_email.replace("{{ trade_name }}", str(row['Trade']))
                    html_email = html_email.replace("{{ base_bid }}", f"{float(row['Base Bid ($)' ] or 0.0):,.2f}")
                    html_email = html_email.replace("{{ inclusions_summary }}", str(row.get('Inclusions/Notes', 'Standard Scope')))
                    html_email = html_email.replace("{{ sender_name }}", "Estimating Team")
                    
                    st.markdown("#### Formatted Email Preview:")
                    components.html(html_email, height=450, scrolling=True)
    else:
        st.info("No bids available to generate correspondence.")