import streamlit as st
import pandas as pd
from datetime import datetime
from farm_backend import FarmLedger 

# Page Configuration
st.set_page_config(page_title="Gohl Farm Ledger", page_icon="🐝", layout="wide")
st.title("🐝 Gohl Beekeeping Operation — Financial & Hive Registry")

# Initialize Google Sheets Connected Backend
ledger = FarmLedger()

# --- PRE-FETCH DATA DICTIONARIES (Fixes NameError Bugs) ---
accounts_df = ledger._get_sheet_data("accounts")
account_options = {}
if not accounts_df.empty:
    account_options = {
        f"{row['account_code']} - {row['account_name']} ({row['account_type']})": row['account_code'] 
        for _, row in accounts_df.iterrows()
    }

yards_df = ledger._get_sheet_data("yards")
df_logs = ledger._get_sheet_data("hive_inventory_logs")
entries_df = ledger._get_sheet_data("journal_entries")


# --- SIDEBAR RUNNING METRICS CONTROLLER ---
st.sidebar.header("📊 Quick Farm Metrics")
if not entries_df.empty and len(entries_df) > 0:
    # Compute active cash position via Pandas
    cash_df = entries_df[entries_df['account_code'] == 1000]
    cash_balance = cash_df['debit'].sum() - cash_df['credit'].sum()
    st.sidebar.metric(label="Corporate Cash Pool", value=f"${cash_balance:,.2f} CAD")
    
    # Compute unpaid family balance via Pandas
    loan_df = entries_df[(entries_df['account_code'] >= 2100) & (entries_df['account_code'] <= 2199)]
    family_owed = loan_df['credit'].sum() - loan_df['debit'].sum()
    st.sidebar.metric(label="Total Owed to Family", value=f"${family_owed:,.2f} CAD", delta="Farm Liability", delta_color="inverse")
else:
    st.sidebar.metric(label="Corporate Cash Pool", value="$0.00 CAD")
    st.sidebar.metric(label="Total Owed to Family", value="$0.00 CAD")


# --- SECTION 1: DOUBLE-ENTRY TRANSACTION LOGGER ---
st.header("📝 Log Double-Entry Transaction")
st.caption("Enforces strict corporate accounting logic. Total Debits must equal Total Credits to post successfully.")

with st.form("transaction_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        tx_date = st.date_input("Transaction Date", datetime.today())
        tx_desc = st.text_input("Description / Memo", placeholder="e.g., Spring Varroa mite treatment purchase")
    with col2:
        tx_member = st.selectbox("Associated Family Member (Optional)", ["None", "C", "P", "M", "H", "S"])
        member_val = None if tx_member == "None" else tx_member

    st.markdown("---")
    
    col_leg1_acc, col_leg1_deb, col_leg1_crd = st.columns([2, 1, 1])
    with col_leg1_acc:
        leg1_account = st.selectbox("Account 1 (Debit Target)", options=list(account_options.keys()), key="leg1")
    with col_leg1_deb:
        leg1_debit = st.number_input("Debit Amount ($)", min_value=0.0, step=10.0, key="l1_deb")
    with col_leg1_crd:
        leg1_credit = st.number_input("Credit Amount ($)", min_value=0.0, step=10.0, key="l1_crd")

    col_leg2_acc, col_leg2_deb, col_leg2_crd = st.columns([2, 1, 1])
    with col_leg2_acc:
        leg2_account = st.selectbox("Account 2 (Credit Target)", options=list(account_options.keys()), key="leg2")
    with col_leg2_deb:
        leg2_debit = st.number_input("Debit Amount ($)", min_value=0.0, step=10.0, key="l2_deb")
    with col_leg2_crd:
        leg2_credit = st.number_input("Credit Amount ($)", min_value=0.0, step=10.0, key="l2_crd")

    submit_button = st.form_submit_button("Post Transaction to Ledger")

    if submit_button:
        legs_payload = [
            {"code": account_options[leg1_account], "debit": leg1_debit, "credit": leg1_credit, "member": member_val},
            {"code": account_options[leg2_account], "debit": leg2_debit, "credit": leg2_credit, "member": member_val}
        ]
        try:
            ledger.log_transaction(
                date_str=tx_date.strftime("%Y-%m-%d"),
                description=tx_desc,
                legs=legs_payload
            )
            st.success("Transaction recorded safely into your connected Google Sheet!")
            st.rerun()
        except ValueError as err:
            st.error(f"❌ Entry Rejected: {err}")


# --- SECTION 2: CLEANED GOOGLE SHEETS AUDIT VIEWS ---
st.header("🔍 Real-Time Ledger Audit & Analysis")
tab1, tab2 = st.tabs(["📋 General Ledger Records", "👥 Shareholder Loan Balances"])

with tab1:
    if not entries_df.empty and len(entries_df) > 0:
        # Merge descriptions cleanly on the fly using Pandas DataFrames
        view_df = pd.merge(entries_df, accounts_df, on="account_code", how="left")
        render_cols = ["entry_id", "transaction_date", "description", "account_name", "debit", "credit", "contributor_name"]
        st.dataframe(view_df[render_cols].sort_values(by="entry_id", ascending=False), use_container_width=True)
    else:
        st.info("No transaction records found in Google Sheet yet.")

with tab2:
    if not entries_df.empty and len(entries_df) > 0:
        loan_entries = entries_df[(entries_df['account_code'] >= 2100) & (entries_df['account_code'] <= 2199)].dropna(subset=['contributor_name'])
        if not loan_entries.empty:
            loan_entries['balance'] = loan_entries['credit'] - loan_entries['debit']
            debt_analysis_df = loan_entries.groupby('contributor_name')['balance'].sum().reset_index()
            debt_analysis_df.columns = ["Family Member", "Total Outstanding Loan (CAD)"]
            st.subheader("Current Unpaid Cash Injections per Family Member")
            st.bar_chart(data=debt_analysis_df, x="Family Member", y="Total Outstanding Loan (CAD)")
            st.table(debt_analysis_df)
        else:
            st.info("No shareholder cash injections tracked yet.")
    else:
        st.info("No shareholder cash injections tracked yet.")


# --- SECTION 3: HIVE & YARD INVENTORY MODULE ---
st.markdown("---")
st.header("🐝 Hive Inventory & Apiary Yard Management")

op_tab1, op_tab2, op_tab3 = st.tabs(["📈 Operations Dashboard", "🚜 Log Field Data", "🗺️ Manage Apiary Yards"])

# TAB 1: OPERATIONAL SNAPSHOTS & CHARTS
with op_tab1:
    if not df_logs.empty and not yards_df.empty:
        inventory_df = pd.merge(df_logs, yards_df, on="yard_id", how="inner")
        inventory_df = inventory_df.sort_values(by=["log_date", "log_id"], ascending=[False, False])
        
        latest_snapshot = inventory_df.sort_values('log_date').groupby('yard_name').last().reset_index()
        
        met_col1, met_col2, met_col3, met_col4 = st.columns(4)
        with met_col1:
            st.metric("Total Apiary Yards", len(latest_snapshot))
        with met_col2:
            st.metric("Total Active Production Hives", int(latest_snapshot['hive_count'].sum()))
        with met_col3:
            st.metric("Total Nucleus Colonies (Nucs)", int(latest_snapshot['nuc_count'].sum()))
        with met_col4:
            st.metric("Total Logged Winter Losses", int(inventory_df['winter_losses'].sum()))

        st.subheader("Yard Distribution & Performance (0-10)")
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.caption("Current Hives per Yard")
            st.bar_chart(data=latest_snapshot, x="yard_name", y="hive_count")
        with col_chart2:
            st.caption("Yard Performance Rating Profile")
            st.bar_chart(data=latest_snapshot, x="yard_name", y="performance_rating")
            
        st.subheader("Historical Field Log Records")
        st.dataframe(inventory_df, use_container_width=True)
    else:
        st.info("No field data has been logged yet.")

# TAB 2: LOG NEW OPERATIONAL INSIGHTS
with op_tab2:
    if not yards_df.empty:
        yard_options = {row['yard_name']: row['yard_id'] for _, row in yards_df.iterrows()}
        with st.form("inventory_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                log_date = st.date_input("Inspection Date", datetime.today(), key="inv_date")
                selected_yard = st.selectbox("Select Apiary Yard Location", options=list(yard_options.keys()))
            with col_b:
                performance = st.slider("Yard Evaluation Score (0 = Collapsing, 10 = Exceptional)", 0, 10, 5)
            
            st.markdown("---")
            col_c, col_d, col_e = st.columns(3)
            with col_c:
                hives = st.number_input("Active Production Hive Count", min_value=0, value=0, step=1)
            with col_d:
                nucs = st.number_input("Nucleus Colony (Nuc) Count", min_value=0, value=0, step=1)
            with col_e:
                losses = st.number_input("Winter Losses Count (Since last cycle)", min_value=0, value=0, step=1)
                
            submit_log = st.form_submit_button("Post Field Log to System")
            if submit_log:
                ledger.log_inventory(
                    date_str=log_date.strftime("%Y-%m-%d"),
                    yard_id=yard_options[selected_yard],
                    hives=hives,
                    nucs=nucs,
                    losses=losses,
                    rating=performance
                )
                st.success(f"Successfully recorded field snapshot for yard: {selected_yard}!")
                st.rerun()
    else:
        st.warning("⚠️ You must add at least one apiary yard in the 'Manage Apiary Yards' tab before logging metrics.")

# TAB 3: LOCATION REGISTER
with op_tab3:
    col_y1, col_y2 = st.columns(2)
    with col_y1:
        st.subheader("Add New Apiary Yard")
        with st.form("yard_form", clear_on_submit=True):
            yard_name = st.text_input("Yard Name (Unique Identifier)", placeholder="e.g., Brandon North")
            yard_notes = st.text_area("Location / Landowner Lease Notes", placeholder="e.g., Property leased for 10 lbs of honey per year.")
            submit_yard = st.form_submit_button("Create Yard")
            if submit_yard and yard_name:
                ledger.add_yard(yard_name, yard_notes)
                st.success(f"Apiary Yard '{yard_name}' successfully saved.")
