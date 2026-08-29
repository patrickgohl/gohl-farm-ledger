import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

class FarmLedger:
    def __init__(self):
        # Establish connection using Streamlit's official GSheets wrapper
        self.conn = st.connection("gsheets", type=GSheetsConnection)
        self._initialize_chart_of_accounts()

    def _get_sheet_data(self, worksheet_name):
        """Helper to fetch fresh dataframe from a specific Google Sheet tab."""
        # 1. Pull the secure URL directly from Streamlit Secrets at runtime
        # This keeps it 100% hidden from your public GitHub repo!
        secure_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        
        # 2. Explicitly pass the url variable inside the connection read handler
        # This completely forces the engine past its internal configuration bugs
        return self.conn.read(spreadsheet=secure_url, worksheet=worksheet_name, ttl=0)


    def _initialize_chart_of_accounts(self):
        """Seeds the standard farm chart of accounts if the sheet is empty."""
        df_accounts = self._get_sheet_data("accounts")
        if df_accounts.empty or len(df_accounts) == 0:
            default_accounts = [
                {"account_code": 1000, "account_name": "Cash - Corporate Checking", "account_type": "Asset"},
                {"account_code": 1200, "account_name": "Equipment - Beekeeping Assets", "account_type": "Asset"},
                {"account_code": 2100, "account_name": "Shareholder Loan - Person C", "account_type": "Liability"},
                {"account_code": 2101, "account_name": "Shareholder Loan - Person P", "account_type": "Liability"},
                {"account_code": 2102, "account_name": "Shareholder Loan - Person M", "account_type": "Liability"},
                {"account_code": 2103, "account_name": "Shareholder Loan - Person H", "account_type": "Liability"},
                {"account_code": 2104, "account_name": "Shareholder Loan - Person S", "account_type": "Liability"},
                {"account_code": 4000, "account_name": "Revenue - Wholesale Honey", "account_type": "Revenue"},
                {"account_code": 4100, "account_name": "Revenue - Retail Sales", "account_type": "Revenue"},
                {"account_code": 5000, "account_name": "Expense - Sugar & Bee Feed", "account_type": "Expense"},
                {"account_code": 5100, "account_name": "Expense - Mite & Varroa Treatments", "account_type": "Expense"},
                {"account_code": 5200, "account_name": "Expense - Person S Stipend", "account_type": "Expense"}
            ]
            df_new = pd.DataFrame(default_accounts)
            self.conn.update(worksheet="accounts", data=df_new)

    def log_transaction(self, date_str, description, legs):
        """Validates and appends a double-entry financial transaction to Google Sheets."""
        total_debit = sum(leg.get('debit', 0.0) for leg in legs)
        total_credit = sum(leg.get('credit', 0.0) for leg in legs)
        
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValueError(f"Unbalanced Transaction! Debits ({total_debit}) must equal Credits ({total_credit}).")
        
        df_entries = self._get_sheet_data("journal_entries")
        next_id = 1 if df_entries.empty or "entry_id" not in df_entries.columns or df_entries["entry_id"].dropna().empty else int(df_entries["entry_id"].max()) + 1
        
        new_rows = []
        for leg in legs:
            new_rows.append({
                "entry_id": next_id,
                "transaction_date": date_str,
                "description": description,
                "account_code": int(leg['code']),
                "debit": float(leg.get('debit', 0.0)),
                "credit": float(leg.get('credit', 0.0)),
                "contributor_name": leg.get('member')
            })
            next_id += 1
            
        df_updated = pd.concat([df_entries, pd.DataFrame(new_rows)], ignore_index=True)
        self.conn.update(worksheet="journal_entries", data=df_updated)

    def add_yard(self, name, notes=""):
        """Appends a new apiary yard to the Google Sheet tab."""
        df_yards = self._get_sheet_data("yards")
        if not df_yards.empty and name in df_yards['yard_name'].values:
            return # Skip if already exists
            
        next_id = 1 if df_yards.empty or "yard_id" not in df_yards.columns or df_yards["yard_id"].dropna().empty else int(df_yards["yard_id"].max()) + 1
        new_yard = pd.DataFrame([{"yard_id": next_id, "yard_name": name, "location_notes": notes}])
        df_updated = pd.concat([df_yards, new_yard], ignore_index=True)
        self.conn.update(worksheet="yards", data=df_updated)

    def log_inventory(self, date_str, yard_id, hives, nucs, losses, rating):
        """Appends field hive metrics to the operational Google Sheet tab."""
        df_logs = self._get_sheet_data("hive_inventory_logs")
        next_id = 1 if df_logs.empty or "log_id" not in df_logs.columns or df_logs["log_id"].dropna().empty else int(df_logs["log_id"].max()) + 1
        
        new_log = pd.DataFrame([{
            "log_id": next_id,
            "log_date": date_str,
            "yard_id": int(yard_id),
            "hive_count": int(hives),
            "nuc_count": int(nucs),
            "winter_losses": int(losses),
            "performance_rating": int(rating)
        }])
        df_updated = pd.concat([df_logs, new_log], ignore_index=True)
        self.conn.update(worksheet="hive_inventory_logs", data=df_updated)
