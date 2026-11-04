import pandas as pd
import sqlite3
from ipumspy import readers


class TableEnvironment:
    def __init__(self, row):
        self.source = row["source"]
        self.db_id = row["db_id"]
        self.data_source_dir = None
        self.sql_augmentation = row["sql_augmentation"]
        self.original_table_name = row["table_name"]
        self.table_name = None
        self.row = row

    def connect(self):
        if self.source == "spider":
            self.data_source_dir = f"raw_data/spider_data/spider_data/test_database/{self.db_id}"
            connection = sqlite3.connect(":memory:")
            disk_conn = sqlite3.connect(f"{self.data_source_dir}/{self.db_id}.sqlite")
            disk_conn.backup(connection)
            cursor = connection.cursor()
            self._execute_augmentation(cursor)
            df = self._create_dataframe(connection)
            return cursor, df
        
        elif self.source == "manual":
            self.data_source_dir = f"raw_data/manual/{self.db_id}"
            ddi = readers.read_ipums_ddi(f"{self.data_source_dir}/{self.db_id}.xml")
            df = readers.read_microdata(ddi, filename=f"{self.data_source_dir}/{self.db_id}.dat")
            connection = sqlite3.connect(f"database_{self.db_id}.db")
            try:
                df.to_sql(name=f"{self.db_id}", con=connection, index=False)
            except:
                print("Created database file")
            cursor = connection.cursor()
            try:
                self._execute_augmentation(cursor)
            except:
                print("Database file already exists")
            return cursor, df

    def _create_dataframe(self, connection):
        df = pd.read_sql_query(f"SELECT * FROM {self.table_name}", connection)
        return df
    
    def _execute_augmentation(self, cursor):
        if not pd.isnull(self.sql_augmentation):
            cursor.execute(self.sql_augmentation)
            cursor.execute(f"DROP TABLE {self.original_table_name};")
            self.table_name = self.row["new_table_name"]
        else:
            self.table_name = self.row["table_name"]

