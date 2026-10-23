"""
Database Manager - Converts CSV files to SQLite database
"""

import sqlite3
import pandas as pd
import os
from pathlib import Path
import config

class DatabaseManager:
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self.data_folder = config.DATA_FOLDER
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        Path("database").mkdir(exist_ok=True)
        Path("schema").mkdir(exist_ok=True)
    
    def get_csv_files(self):
        """Get all CSV files from Data folder"""
        csv_files = []
        for file in os.listdir(self.data_folder):
            if file.endswith('.csv'):
                csv_files.append(os.path.join(self.data_folder, file))
        return csv_files
    
    def clean_table_name(self, filename):
        """Convert filename to clean table name"""
        table_name = os.path.basename(filename).replace('.csv', '')
        return table_name.replace(' ', '_').replace('-', '_')
    
    def infer_primary_key(self, df, table_name):
        """Infer primary key from column names"""
        # Common PK patterns
        pk_candidates = [
            f"{table_name}ID",
            "ID",
            f"{table_name}_ID",
            "id",
            f"{table_name.lower()}id"
        ]
        
        for col in df.columns:
            if col in pk_candidates:
                return col
        
        # Check for columns ending with 'ID'
        for col in df.columns:
            if col.endswith('ID') or col.endswith('Id'):
                return col
        
        return None
    
    def get_column_type(self, series):
        """Infer SQLite type from pandas series"""
        dtype = str(series.dtype)
        
        if 'int' in dtype:
            return 'INTEGER'
        elif 'float' in dtype:
            return 'REAL'
        elif 'datetime' in dtype or 'date' in dtype:
            return 'TEXT'  # Store dates as text
        else:
            return 'TEXT'
    
    def create_table_schema(self, df, table_name, primary_key):
        """Generate CREATE TABLE statement"""
        columns = []
        
        for col in df.columns:
            col_type = self.get_column_type(df[col])
            if col == primary_key:
                columns.append(f"{col} {col_type} PRIMARY KEY")
            else:
                columns.append(f"{col} {col_type}")
        
        schema = f"CREATE TABLE IF NOT EXISTS {table_name} (\n  "
        schema += ",\n  ".join(columns)
        schema += "\n)"
        
        return schema
    
    def clean_column_name(self, col_name):
        """Clean column name to be SQL-safe"""
        import re
        # Replace spaces and special chars with underscore
        col_name = re.sub(r'[^a-zA-Z0-9_]', '_', str(col_name))
        # Remove multiple consecutive underscores
        col_name = re.sub(r'_+', '_', col_name)
        # Prefix if starts with number
        if col_name[0].isdigit():
            col_name = 'col_' + col_name
        # Remove trailing underscore
        col_name = col_name.strip('_')
        return col_name
    
    def import_csv_to_db(self, csv_file):
        """Import single CSV file to database"""
        print(f"Importing {csv_file}...")
        
        # Read CSV
        df = pd.read_csv(csv_file)
        
        # Clean all column names
        df.columns = [self.clean_column_name(col) for col in df.columns]
        
        # Handle duplicate column names
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            dup_indices = cols[cols == dup].index.tolist()
            for i, idx in enumerate(dup_indices[1:], start=1):
                cols[idx] = f"{dup}_{i}"
        df.columns = cols
        
        table_name = self.clean_table_name(csv_file)
        
        # Infer primary key
        primary_key = self.infer_primary_key(df, table_name)
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table
        schema = self.create_table_schema(df, table_name, primary_key)
        cursor.execute(schema)
        
        # Import data
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        
        conn.commit()
        conn.close()
        
        print(f"  ✓ Imported {len(df)} rows into {table_name}")
        return table_name
    
    def create_indexes(self):
        """Create indexes on foreign key columns"""
        print("\nCreating indexes...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for (table_name,) in tables:
            # Get columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # Create index on columns ending with 'ID' (likely FKs)
            for col in columns:
                col_name = col[1]
                if col_name.endswith('ID') and col_name != col[1]:  # Not PK
                    try:
                        idx_name = f"idx_{table_name}_{col_name}"
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({col_name})")
                        print(f"  ✓ Created index: {idx_name}")
                    except:
                        pass
        
        conn.commit()
        conn.close()
    
    def build_database(self):
        """Build complete database from CSV files"""
        print("=" * 60)
        print("Building Database from CSV files...")
        print("=" * 60)
        
        csv_files = self.get_csv_files()
        print(f"\nFound {len(csv_files)} CSV files\n")
        
        tables = []
        for csv_file in csv_files:
            table_name = self.import_csv_to_db(csv_file)
            tables.append(table_name)
        
        self.create_indexes()
        
        print("\n" + "=" * 60)
        print(f"✓ Database created successfully: {self.db_path}")
        print(f"✓ Total tables: {len(tables)}")
        print("=" * 60)
        
        return tables
    
    def get_table_info(self, table_name):
        """Get table schema information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'columns': columns,
            'row_count': row_count
        }

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.build_database()
