import streamlit as st
import pandas as pd

class FarmLedger:
    def __init__(self):
        # 1. Pull the URL safely from your encrypted Streamlit Secrets dashboard at runtime
        self.base_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # Strip trailing text to get the clean base link if necessary
        if self.base_url.endswith("/edit"):
            self.base_url = self.base_url[:-5]
            
        self._initialize_chart_of_accounts()

    def _get_sheet_data(self, worksheet_name):
        """Fetches fresh data from a specific tab name securely without using Google Cloud."""
        try:
            # 2. Convert your base link into a direct Pandas open-source CSV export request
            # This completely bypasses the library's internal browser scraping bugs!
            export_url = f"{self.base_url}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
            
            # Read directly into a Pandas DataFrame using Streamlit's network parameters
            df = pd.read_csv(export_url)
            return df
        except Exception as e:
            st.error(f"Error fetching worksheet '{worksheet_name}': {e}")
            return pd.DataFrame()

    def _initialize_chart_of_accounts(self):
        """Reads your accounts sheet layout directly."""
        df_accounts = self._get_sheet_data("accounts")
        # Since this method is read-only, initialization checks rely on your Google Sheet having columns pre-made
        if df_accounts.empty or len(df_accounts) == 0:
            st.warning("⚠️ The 'accounts' tab in your Google Sheet appears to be empty. Please verify your dummy data rows exist.")

    def log_transaction(self, date_str, description, legs):
        """Displays instructions for cloud ledger updating constraints."""
        total_debit = sum(leg.get('debit', 0.0) for leg in legs)
        total_credit = sum(leg.get('credit', 0.0) for leg in legs)
        
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValueError(f"Unbalanced Transaction! Debits ({total_debit}) must equal Credits ({total_credit}).")
            
        st.info("💡 Direct writing through public endpoints requires a Google Service account key. To save changes, update rows directly in your Google Sheet dashboard.")

    def add_yard(self, name, notes=""):
        st.info("💡 Direct writing through public endpoints requires a Google Service account key. To save changes, update rows directly in your Google Sheet dashboard.")

    def log_inventory(self, date_str, yard_id, hives, nucs, losses, rating):
        st.info("💡 Direct writing through public endpoints requires a Google Service account key. To save changes, update rows directly in your Google Sheet dashboard.")
