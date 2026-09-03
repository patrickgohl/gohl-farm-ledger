import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text

class FarmLedger:
    def __init__(self):
        # 1. Connect natively to the writeable database defined in your Secrets
        self.conn = st.connection("db", type="sql")
        self._initialize_database_tables()

    def _execute_query(self, query_string, params=None):
        """Helper to run write/insert operations securely."""
        with self.conn.session as session:
            session.execute(text(query_string), params or {})
            session.commit()

    def _get_sheet_data(self, table_name):
        """Helper to safely fetch a table as a Pandas DataFrame."""
        try:
            return self.conn.query(f"SELECT * FROM {table_name};", ttl=0)
        except Exception:
            # Return empty dataframe if table doesn't exist yet
            return pd.DataFrame()

    def _initialize_database_tables(self):
        """Builds all operational and financial tables with clean, permanent PostgreSQL relations."""
        # Create Accounts Table
        self._execute_query("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_code INTEGER PRIMARY KEY,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL
        );
        """)
        
        # Create Journal Entries Table (Using standard SERIAL for cloud auto-increment)
        self._execute_query("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            entry_id SERIAL PRIMARY KEY,
            transaction_date TEXT NOT NULL,
            description TEXT NOT NULL,
            account_code INTEGER NOT NULL,
            debit REAL DEFAULT 0.0,
            credit REAL DEFAULT 0.0,
            contributor_name TEXT
        );
        """)
        
        # Create Yards Table
        self._execute_query("""
        CREATE TABLE IF NOT EXISTS yards (
            yard_id SERIAL PRIMARY KEY,
            yard_name TEXT NOT NULL UNIQUE,
            location_notes TEXT
        );
        """)

        # Create Hive Inventory Logs Table
        self._execute_query("""
        CREATE TABLE IF NOT EXISTS hive_inventory_logs (
            log_id SERIAL PRIMARY KEY,
            log_date TEXT NOT NULL,
            yard_id INTEGER NOT NULL,
            hive_count INTEGER DEFAULT 0,
            nuc_count INTEGER DEFAULT 0,
            winter_losses INTEGER DEFAULT 0,
            performance_rating INTEGER
        );
        """)
        
        self._seed_chart_of_accounts()


    def _seed_chart_of_accounts(self):
        """Seeds default Manitoba bee farm accounts if table is completely fresh."""
        df_accounts = self._get_sheet_data("accounts")
        if df_accounts.empty or len(df_accounts) == 0:
            default_accounts = [
                (1000, "Cash - Corporate Checking", "Asset"),
                (1200, "Equipment - Beekeeping Assets", "Asset"),
                (2100, "Shareholder Loan - Person C", "Liability"),
                (2101, "Shareholder Loan - Person P", "Liability"),
                (2102, "Shareholder Loan - Person M", "Liability"),
                (2103, "Shareholder Loan - Person H", "Liability"),
                (2104, "Shareholder Loan - Person S", "Liability"),
                (4000, "Revenue - Wholesale Honey", "Revenue"),
                (4100, "Revenue - Retail Sales", "Revenue"),
                (5000, "Expense - Sugar & Bee Feed", "Expense"),
                (5100, "Expense - Mite & Varroa Treatments", "Expense"),
                (5200, "Expense - Person S Stipend", "Expense")
            ]
            for code, name, acc_type in default_accounts:
                self._execute_query(
                    "INSERT OR IGNORE INTO accounts VALUES (:code, :name, :type);",
                    {"code": code, "name": name, "type": acc_type}
                )

    def log_transaction(self, date_str, description, legs):
        """Validates double-entry logic and saves transactions to the database."""
        total_debit = sum(leg.get('debit', 0.0) for leg in legs)
        total_credit = sum(leg.get('credit', 0.0) for leg in legs)
        
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValueError(f"Unbalanced Transaction! Debits ({total_debit}) must equal Credits ({total_credit}).")
        
        for leg in legs:
            self._execute_query("""
                INSERT INTO journal_entries (transaction_date, description, account_code, debit, credit, contributor_name)
                VALUES (:date, :desc, :code, :debit, :credit, :member);
            """, {
                "date": date_str, "desc": description, "code": int(leg['code']),
                "debit": float(leg.get('debit', 0.0)), "credit": float(leg.get('credit', 0.0)), "member": leg.get('member')
            })

    def add_yard(self, name, notes=""):
        """Saves a new apiary yard location."""
        self._execute_query(
            "INSERT OR IGNORE INTO yards (yard_name, location_notes) VALUES (:name, :notes);",
            {"name": name, "notes": notes}
        )

    def log_inventory(self, date_str, yard_id, hives, nucs, losses, rating):
        """Saves physical hive metrics safely with explicitly matched parameter binds."""
        self._execute_query("""
            INSERT INTO hive_inventory_logs (log_date, yard_id, hive_count, nuc_count, winter_losses, performance_rating)
            VALUES (:date, :yard_id, :hives, :nucs, :losses, :rating);
        """, {
            "date": date_str, 
            "yard_id": int(yard_id), 
            "hives": int(hives),
            "nucs": int(nucs),       # Fixed to match :nucs perfectly
            "losses": int(losses),   # Fixed to match :losses perfectly
            "rating": int(rating)
        })

    def export_raw_db_bytes(self):
        """Reads the raw sqlite database file from disk and returns a binary byte stream for downloading."""
        import io
        import os
        
        db_path = "farm_production.db"
        
        # Fallback check to ensure the file exists on the cloud server container
        if os.path.exists(db_path):
            with open(db_path, "rb") as f:
                # Read raw binary data into a stream
                return io.BytesIO(f.read())
        else:
            # Fallback stream if file is not generated yet
            return io.BytesIO(b"No database file generated on disk yet.")

    def delete_journal_entry(self, entry_id):
        """Permanently removes a specific financial journal entry by ID."""
        self._execute_query("DELETE FROM journal_entries WHERE entry_id = :id;", {"id": int(entry_id)})

    def delete_inventory_log(self, log_id):
        """Permanently removes a specific hive inventory inspection log by ID."""
        self._execute_query("DELETE FROM hive_inventory_logs WHERE log_id = :id;", {"id": int(log_id)})
