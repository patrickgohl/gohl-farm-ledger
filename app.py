import streamlit as st
import pandas as pd
from datetime import datetime
from farm_backend import FarmLedger 

# Page Configuration
st.set_page_config(page_title="Gohl Farm Ledger", page_icon="🐝", layout="wide")
st.title("🐝 Gohl Beekeeping Operation — Financial & Hive Registry")

# Initialize Backend Connection
ledger = FarmLedger()

# Pre-fetch DataFrames
accounts_df = ledger._get_sheet_data("accounts")
yards_df = ledger._get_sheet_data("yards")
df_logs = ledger._get_sheet_data("hive_inventory_logs")
entries_df = ledger._get_sheet_data("journal_entries")

# Format dropdown configurations safely
account_options = {}
if not accounts_df.empty:
    account_options = {
        f"{row['account_code']} - {row['account_name']} ({row['account_type']})": row['account_code'] 
        for _, row in accounts_df.iterrows()
    }

# --- UNIFIED SIDEBAR CONTROLLER (METRICS, BACKUPS, & ADMIN) ---
st.sidebar.header("📊 Quick Farm Metrics")

if not entries_df.empty and len(entries_df) > 0:
    cash_df = entries_df[entries_df['account_code'] == 1000]
    cash_balance = cash_df['debit'].sum() - cash_df['credit'].sum()
    st.sidebar.metric(label="Corporate Cash Pool", value=f"${cash_balance:,.2f} CAD")
    
    loan_df = entries_df[(entries_df['account_code'] >= 2100) & (entries_df['account_code'] <= 2199)]
    family_owed = loan_df['credit'].sum() - loan_df['debit'].sum()
    st.sidebar.metric(label="Total Owed to Family", value=f"${family_owed:,.2f} CAD", delta="Farm Liability", delta_color="inverse")
else:
    st.sidebar.metric(label="Corporate Cash Pool", value="$0.00 CAD")
    st.sidebar.metric(label="Total Owed to Family", value="$0.00 CAD")

# --- SYSTEM BACKUPS SNIPPET ---
st.sidebar.markdown("---")
st.sidebar.subheader("💾 System Backups")
st.sidebar.caption("Download a safe, raw relational data snapshot of all family records.")

try:
    raw_db_bytes = ledger.export_raw_db_bytes()
    timestamp = datetime.today().strftime("%Y-%m-%d")
    st.sidebar.download_button(
        label="⬇️ Download Ledger (.CSV)",
        data=raw_db_bytes,
        file_name=f"gohl_ledger_backup_{timestamp}.csv",
        mime="text/csv",
        use_container_width=True
    )
except Exception as e:
    st.sidebar.error(f"Backup Error: {e}")

# --- SECURE ADMIN SYSTEM GATEKEEPER ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 System Administration")

# Initialize a session state token to hold password verification status
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

# Password input text box explicitly declared inside the sidebar wrapper
admin_password_input = st.sidebar.text_input("Enter Admin Password", type="password", key="admin_pwd_box")

if admin_password_input == st.secrets["admin"]["password"]:
    st.session_state["admin_authenticated"] = True
    st.sidebar.success("Admin access granted!")
else:
    st.session_state["admin_authenticated"] = False
    if admin_password_input:
        st.sidebar.error("Incorrect password.")


# --- SECTION 1: DYNAMIC DOUBLE-ENTRY LOGGER ---
st.header("📝 Log General Ledger Transaction")
st.caption("Select any target accounts from the Chart of Accounts to post a balanced transaction.")

with st.form("transaction_form", clear_on_submit=True):
    col_meta1, col_meta2, col_meta3 = st.columns([1, 2, 1])
    with col_meta1:
        tx_date = st.date_input("Transaction Date", datetime.today())
    with col_meta2:
        tx_desc = st.text_input("Transaction Description / Custom Memo", placeholder="e.g., Bought sugar syrup from local cooperative")
    with col_meta3:
        tx_member = st.selectbox("Associated Partner (Optional)", ["None", "C", "P", "M", "H", "S"])
        member_val = None if tx_member == "None" else tx_member

    st.markdown("##### Entry Balancing Grid")
    
    # LEG 1: Row input for the first account
    col_l1_acc, col_l1_deb, col_l1_crd = st.columns([2, 1, 1])
    with col_l1_acc:
        leg1_account = st.selectbox("Target Account 1", options=list(account_options.keys()), key="leg1_sel")
    with col_l1_deb:
        leg1_debit = st.number_input("Debit Amount 1 ($)", min_value=0.0, value=0.0, step=1.0, key="l1_deb")
    with col_l1_crd:
        leg1_credit = st.number_input("Credit Amount 1 ($)", min_value=0.0, value=0.0, step=1.0, key="l1_crd")

    # LEG 2: Row input for the counterbalancing account
    col_l2_acc, col_l2_deb, col_l2_crd = st.columns([2, 1, 1])
    with col_l2_acc:
        leg2_account = st.selectbox("Target Account 2", options=list(account_options.keys()), key="leg2_sel")
    with col_l2_deb:
        leg2_debit = st.number_input("Debit Amount 2 ($)", min_value=0.0, value=0.0, step=1.0, key="l2_deb")
    with col_l2_crd:
        leg2_credit = st.number_input("Credit Amount 2 ($)", min_value=0.0, value=0.0, step=1.0, key="l2_crd")

    submit_button = st.form_submit_button("Post Balanced Transaction to Supabase")

    if submit_button:
        # Construct parameters passing raw integer codes extracted from selection dict
        legs_payload = [
            {"code": account_options[leg1_account], "debit": leg1_debit, "credit": leg1_credit, "member": member_val},
            {"code": account_options[leg2_account], "debit": leg2_debit, "credit": leg2_credit, "member": member_val}
        ]
        
        try:
            # Pass data down into backend validation engine
            ledger.log_transaction(
                date_str=tx_date.strftime("%Y-%m-%d"),
                description=tx_desc if tx_desc else "General Journal Entry",
                legs=legs_payload
            )
            st.success("Transaction posted and balanced successfully on Supabase cloud database!")
            st.rerun()
        except ValueError as err:
            st.error(f"❌ Entry Rejected: {err}")



# --- SECTION 2: AUDIT TRAILS & FINANCIAL STATEMENTS ---
st.header("🔍 Real-Time Ledger Audit & Analysis")
tab1, tab2, tab3 = st.tabs([
    "📋 General Ledger Records", 
    "👥 Shareholder Loan Balances", 
    "📊 Income Statement (P&L)"
])

# --- TAB 1: GENERAL LEDGER AUDIT RECORDS ---
with tab1:
    if not entries_df.empty and len(entries_df) > 0:
        view_df = pd.merge(entries_df, accounts_df, on="account_code", how="left")
        render_cols = ["entry_id", "transaction_date", "description", "account_name", "debit", "credit", "contributor_name"]
        st.dataframe(view_df[render_cols].sort_values(by="entry_id", ascending=False), use_container_width=True)
    else:
        st.info("No transaction records found in database yet.")

# --- TAB 2: SHAREHOLDER LOAN BALANCE MONITOR ---
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

# --- TAB 3: DYNAMIC INCOME STATEMENT (P&L) ---
with tab3:
    st.subheader("🗓️ Dynamic Farm Income Statement")
    st.caption("Calculates operational yields, variable costs, and net farm surplus dynamically using live ledger entries.")

    if not entries_df.empty and len(entries_df) > 0:
        # Merge accounts data to get classifications mapping
        pl_df = pd.merge(entries_df, accounts_df, on="account_code", how="inner")
        
        # 1. PROCESS REVENUES (4000 - 4999) -> Revenue increases with CREDITS
        rev_entries = pl_df[(pl_df['account_code'] >= 4000) & (pl_df['account_code'] <= 4999)]
        rev_grouped = rev_entries.groupby('account_name')['credit'].sum().reset_index()
        rev_grouped.columns = ["Line Item", "Amount (CAD)"]
        total_revenue = rev_grouped["Amount (CAD)"].sum()
        
        # 2. PROCESS EXPENSES (5000 - 5999) -> Expenses increase with DEBITS
        exp_entries = pl_df[(pl_df['account_code'] >= 5000) & (pl_df['account_code'] <= 5999)]
        exp_grouped = exp_entries.groupby('account_name')['debit'].sum().reset_index()
        exp_grouped.columns = ["Line Item", "Amount (CAD)"]
        total_expenses = exp_grouped["Amount (CAD)"].sum()
        
        # 3. CALCULATE BOTTOM LINE
        net_farm_income = total_revenue - total_expenses
        
        # Display Top-Level Performance Summary Metrics
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("Gross Agricultural Revenue", f"${total_revenue:,.2f} CAD")
        with m_col2:
            st.metric("Total Operating Expenses", f"${total_expenses:,.2f} CAD", delta="- Costs", delta_color="inverse")
        with m_col3:
            # Color indicator handles loss vs surplus state beautifully
            color_state = "normal" if net_farm_income >= 0 else "inverse"
            st.metric("Net Farm Surplus / Deficit", f"${net_farm_income:,.2f} CAD", delta="Net Income", delta_color=color_state)
            
        st.markdown("---")
        
        # Detailed Statement Views Layout Grid Split
        stmt_col1, stmt_col2 = st.columns(2)
        
        with stmt_col1:
            st.markdown("### 📥 Revenue Streams Breakdown")
            if total_revenue > 0:
                st.dataframe(rev_grouped, use_container_width=True, hide_index=True)
            else:
                st.info("No revenue streams logged for this period yet.")
                
        with stmt_col2:
            st.markdown("### 📤 Operating Costs Breakdown")
            if total_expenses > 0:
                st.dataframe(exp_grouped, use_container_width=True, hide_index=True)
            else:
                st.info("No variable farm expenses logged for this period yet.")
        
        # Visual breakdown layout helper using horizontal bar chart logic mapping
        if total_revenue > 0 or total_expenses > 0:
            st.markdown("---")
            st.markdown("### 📊 Structural Overview: Revenue vs Expenses")
            summary_viz_df = pd.DataFrame([
                {"Metric": "Gross Revenue", "Amount (CAD)": total_revenue},
                {"Metric": "Total Expenses", "Amount (CAD)": total_expenses}
            ])
            st.bar_chart(data=summary_viz_df, x="Metric", y="Amount (CAD)")
    else:
        st.info("Insufficient data available. Log revenue or expense entries to generate financial statements.")


# --- SECTION 3: OPERATIONS & HIVES ---
st.markdown("---")
st.header("🐝 Hive Inventory & Apiary Yard Management")

op_tab1, op_tab2, op_tab3 = st.tabs(["📈 Operations Dashboard", "🚜 Log Field Data", "🗺️ Manage Apiary Yards"])

with op_tab1:
    if not df_logs.empty and not yards_df.empty:
        inventory_df = pd.merge(df_logs, yards_df, on="yard_id", how="inner")
        latest_snapshot = inventory_df.sort_values('log_date').groupby('yard_name').last().reset_index()
        
        met_col1, met_col2, met_col3, met_col4 = st.columns(4)
        with met_col1: st.metric("Total Apiary Yards", len(latest_snapshot))
        with met_col2: st.metric("Active Production Hives", int(latest_snapshot['hive_count'].sum()))
        with met_col3: st.metric("Nucleus Colonies (Nucs)", int(latest_snapshot['nuc_count'].sum()))
        with met_col4: st.metric("Logged Hive Losses", int(inventory_df['hive_losses'].sum()))

        st.subheader("Yard Distribution")
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1: st.bar_chart(data=latest_snapshot, x="yard_name", y="hive_count")
        with col_chart2: st.bar_chart(data=latest_snapshot, x="yard_name", y="performance_rating")
        st.dataframe(inventory_df, use_container_width=True)
    else:
        st.info("No field data has been logged yet.")

with op_tab2:
    if not yards_df.empty:
        yard_options = {row['yard_name']: row['yard_id'] for _, row in yards_df.iterrows()}
        with st.form("inventory_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                log_date = st.date_input("Inspection Date", datetime.today(), key="inv_date")
                selected_yard = st.selectbox("Select Apiary Yard Location", options=list(yard_options.keys()))
            with col_b:
                performance = st.slider("Yard Evaluation Score (0-10)", 0, 10, 5)
            
            st.markdown("---")
            col_c, col_d, col_e = st.columns(3)
            with col_c: hives = st.number_input("Active Production Hive Count", min_value=0, step=1)
            with col_d: nucs = st.number_input("Nucleus Colony (Nuc) Count", min_value=0, step=1)
            with col_e: losses = st.number_input("Hive Losses Count", min_value=0, step=1)
                
            submit_log = st.form_submit_button("Post Field Log to System")
            if submit_log:
                ledger.log_inventory(log_date.strftime("%Y-%m-%d"), yard_options[selected_yard], hives, nucs, losses, performance)
                st.success("Field snapshot recorded successfully!")
                st.rerun()
    else:
        st.warning("⚠️ Add an apiary yard first before logging field counts.")

with op_tab3:
    col_y1, col_y2 = st.columns(2)
    with col_y1:
        st.subheader("Add New Apiary Yard")
        with st.form("yard_form", clear_on_submit=True):
            yard_name = st.text_input("Yard Name", placeholder="e.g., Brandon North")
            yard_notes = st.text_area("Location Notes")
            submit_yard = st.form_submit_button("Create Yard")
            if submit_yard and yard_name:
                ledger.add_yard(yard_name, yard_notes)
                st.success(f"Apiary Yard '{yard_name}' successfully saved.")
                st.rerun()
    with col_y2:
        st.subheader("Registered Apiary Locations")
        if not yards_df.empty: st.dataframe(yards_df, use_container_width=True)



# --- BOTTOM OF APP.PY: ADMINISTRATIVE TOOL PANEL RENDERER ---
if st.session_state["admin_authenticated"]:
    st.markdown("---")
    st.header("🛠️ Admin Data Management Tools")
    st.caption("Permanently clear mistakes or bad entries from the farm database records.")
    
    adm_col1, adm_col2 = st.columns(2)
    
    with adm_col1:
        st.subheader("Disposed Financial Records")
        if not entries_df.empty and len(entries_df) > 0:
            tx_to_delete = st.selectbox(
                "Select Transaction ID to Remove", 
                options=sorted(entries_df["entry_id"].unique(), reverse=True)
            )
            preview_tx = entries_df[entries_df["entry_id"] == tx_to_delete]
            st.warning(f"Target Memo: '{preview_tx['description'].values}'")
            
            if st.button("🚨 Permanently Delete Transaction", key="btn_del_tx"):
                ledger.delete_journal_entry(tx_to_delete)
                st.success(f"Transaction ID {tx_to_delete} completely erased.")
                st.rerun()
        else:
            st.info("No transaction records available to delete.")

    with adm_col2:
        st.subheader("Disposed Hive Inventory Logs")
        if not df_logs.empty and len(df_logs) > 0 and not yards_df.empty:
            log_preview_df = pd.merge(df_logs, yards_df, on="yard_id", how="inner")
            log_options = {
                f"Log #{row['log_id']} | {row['log_date']} - {row['yard_name']}": row['log_id']
                for _, row in log_preview_df.iterrows()
            }
            selected_log_label = st.selectbox("Select Hive Field Log to Remove", options=list(log_options.keys()))
            target_log_id = log_options[selected_log_label]
            
            if st.button("🚨 Permanently Delete Field Log", key="btn_del_log"):
                ledger.delete_inventory_log(target_log_id)
                st.success(f"Field Log Entry completely erased.")
                st.rerun()
        else:
            st.info("No hive field inspection logs available to delete.")
