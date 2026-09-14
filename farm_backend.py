import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

class FarmLedger:
    def __init__(self):
        # 1. Fetch the custom key mapping array directly from your Streamlit secrets
        db_secrets = st.secrets["connections"]["db"]
        
        # 2. Import SQLAlchemy's native connection parameters builder object
        from sqlalchemy.engine import URL
        
        # 3. Create a structured database object passing every variable explicitly.
        # This completely stops the engine from attempting string decoding checks!
        object_url = URL.create(
            drivername="postgresql+psycopg2",
            username=db_secrets["db_user"],
            password=db_secrets["db_pass"], 
            host=db_secrets["db_host"],
            port=int(db_secrets["db_port"]), 
            database=db_secrets["db_name"],
            query={"sslmode": "require"}
        )
        
        # 4. Initialize the true native engine using the object structure mapping
        self.engine = create_engine(object_url, pool_pre_ping=True)
        self._initialize_database_tables()




    def _execute_query(self, query_string, params=None):
        """Helper to run write/insert operations securely using a connection pool context manager."""
        with self.engine.begin() as conn:
            conn.execute(text(query_string), params or {})

    def _get_sheet_data(self, table_name):
        """Helper to safely fetch a table as a clean Pandas DataFrame using raw text SQL queries."""
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(text(f"SELECT * FROM {table_name};"), conn)
                return df
        except Exception:
            # Return empty dataframe if the table doesn't exist yet
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
        
        # Create Journal Entries Table
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
            hive_losses INTEGER DEFAULT 0,
            performance_rating INTEGER
        );
        """)
        
        self._seed_chart_of_accounts()

    def _seed_chart_of_accounts(self):
        """Seeds a standard, flexible framework covering all 5 core accounting pillars."""
        df_accounts = self._get_sheet_data("accounts")
        if df_accounts.empty or len(df_accounts) == 0:
            default_accounts = [
                # --- ASSETS (1000 - 1999) ---
                (1000, "Cash - Corporate Checking", "Asset"),
                (1100, "Inventory - Honey & Hive Products", "Asset"),
                (1200, "Property & Land Assets", "Asset"),
                (1300, "Equipment - Beekeeping Infrastructure", "Asset"),
                
                # --- LIABILITIES (2000 - 2999) ---
                (2000, "Accounts Payable / Operational Debt", "Liability"),
                (2050, "Farm Mortgage Payable", "Liability"),
                (2100, "Shareholder Loan - Person C", "Liability"),
                (2101, "Shareholder Loan - Person P", "Liability"),
                (2102, "Shareholder Loan - Person M", "Liability"),
                (2103, "Shareholder Loan - Person H", "Liability"),
                (2104, "Shareholder Loan - Person S", "Liability"),
                
                # --- EQUITY (3000 - 3999) ---
                (3000, "Common Share Capital", "Equity"),
                (3100, "Retained Earnings", "Equity"),
                
                # --- REVENUE (4000 - 4999) ---
                (4000, "Revenue - Wholesale Bulk Honey", "Revenue"),
                (4100, "Revenue - Retail / Direct Sales", "Revenue"),
                (4200, "Revenue - Pollination Services", "Revenue"),
                (4300, "Revenue - Livestock & Nuc Sales", "Revenue"),
                
                # --- EXPENSES (5000 - 5999) ---
                (5000, "Expense - Feed, Sugar & Syrup", "Expense"),
                (5100, "Expense - Varroa & Mite Treatments", "Expense"),
                (5200, "Expense - Labor & Person S Salary", "Expense"),
                (5300, "Expense - Equipment Fuel & Maintenance", "Expense"),
                (5400, "Expense - Land Rent / Lease Costs", "Expense"),
                (5500, "Expense - Bank Interest & Mortgage Fees", "Expense")
            ]
            for code, name, acc_type in default_accounts:
                self._execute_query(
                    """INSERT INTO accounts (account_code, account_name, account_type) 
                       VALUES (:code, :name, :type) 
                       ON CONFLICT (account_code) DO NOTHING;""",
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
            "INSERT INTO yards (yard_name, location_notes) VALUES (:name, :notes) ON CONFLICT (yard_name) DO NOTHING;",
            {"name": name, "notes": notes}
        )

    def log_inventory(self, date_str, yard_id, hives, nucs, losses, rating):
        """Saves physical hive metrics securely with explicitly matched parameter binds."""
        self._execute_query("""
            INSERT INTO hive_inventory_logs (log_date, yard_id, hive_count, nuc_count, hive_losses, performance_rating)
            VALUES (:date, :yard_id, :hives, :nucs, :losses, :rating);
        """, {
            "date": date_str, "yard_id": int(yard_id), "hives": int(hives),
            "nucs": int(nucs), "losses": int(losses), "rating": int(rating)
        })

    def delete_journal_entry(self, entry_id):
        self._execute_query("DELETE FROM journal_entries WHERE entry_id = :id;", {"id": int(entry_id)})

    def delete_inventory_log(self, log_id):
        self._execute_query("DELETE FROM hive_inventory_logs WHERE log_id = :id;", {"id": int(log_id)})

    def export_raw_db_bytes(self):
        """Compiles database records to CSV layout format since a local .db file no longer exists in a cloud environment."""
        import io
        csv_buffer = io.StringIO()
        df = self._get_sheet_data("journal_entries")
        df.to_csv(csv_buffer, index=False)
        return io.BytesIO(csv_buffer.getvalue().encode('utf-8'))

    def batch_import_inventory_csv(self, uploaded_df):
        """Validates and appends a batch dataframe of field logs to the database."""
        # 1. Standardize column names to prevent lowercase/uppercase mapping errors
        uploaded_df.columns = uploaded_df.columns.str.strip().str.lower()
        
        required_cols = ["log_date", "yard_name", "hive_count", "nuc_count", "hive_losses", "performance_rating"]
        missing_cols = [col for col in required_cols if col not in uploaded_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")
            
        # 2. Fetch fresh yard mapping keys from the database
        yards_df = self._get_sheet_data("yards")
        if yards_df.empty:
            raise ValueError("No yards registered in the system yet. Please add apiary yards first.")
            
        yard_mapping = dict(zip(yards_df['yard_name'].str.strip(), yards_df['yard_id']))
        
        # 3. Stream through rows and insert them cleanly into Supabase
        success_count = 0
        for _, row in uploaded_df.iterrows():
            clean_yard_name = str(row['yard_name']).strip()
            
            # Match yard name to its database ID
            if clean_yard_name not in yard_mapping:
                continue # Skip or handle unregistered yards gracefully
                
            self.log_inventory(
                date_str=str(row['log_date']).strip(),
                yard_id=int(yard_mapping[clean_yard_name]),
                hives=int(row['hive_count']),
                nucs=int(row['nuc_count']),
                losses=int(row['hive_losses']),
                rating=int(row['performance_rating'])
            )
            success_count += 1
            
        return success_count

    def batch_delete_inventory_by_yard(self, yard_id):
        """Removes ALL hive inventory inspection records associated with a specific yard."""
        self._execute_query("DELETE FROM hive_inventory_logs WHERE yard_id = :id;", {"id": int(yard_id)})

    def batch_delete_inventory_by_year(self, year_int):
        """Removes ALL hive inventory inspection records posted during a specific calendar year."""
        # Using string matching rules to parse the text-formatted log_date column safely
        year_match = f"{year_int}%"
        self._execute_query("DELETE FROM hive_inventory_logs WHERE log_date LIKE :year_match;", {"year_match": year_match})

    def batch_delete_transactions_by_year(self, year_int):
        """Removes ALL financial journal transactions posted during a specific calendar year."""
        year_match = f"{year_int}%"
        self._execute_query("DELETE FROM journal_entries WHERE transaction_date LIKE :year_match;", {"year_match": year_match})
