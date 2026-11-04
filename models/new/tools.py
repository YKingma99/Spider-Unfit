from google.genai import types
import tempfile
import shutil
import subprocess
import os
import sqlite3
import pandas as pd
import sys

def count_rows_where(table_name, column_name, filter_condition, cursor):
    cursor.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} {filter_condition}"
    )

    count = cursor.fetchone()
    return count

def sample_values(table_name, column_name, cursor, limit=4):
    cursor.execute(
        f"SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit};"
    )
    return cursor.fetchall()

def run_sql(cursor, query: str):
    cursor.execute(query)
    result = cursor.fetchall()
    return result

def run_python(code: str, source_data_dir: str, df):
    with tempfile.TemporaryDirectory() as workdir:
        shutil.copytree(source_data_dir,
            os.path.join(workdir, "data")
        )
        script_path = os.path.join(workdir, "script.py")
        df_path = os.path.join(workdir, "df.pkl")

        df.to_pickle(df_path)

        wrapper = f"""
import pandas as pd

df = pd.read_pickle(r"{df_path}")

{code}
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapper)

        result = subprocess.run(
            [sys.executable, script_path],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False
        )

        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }

FUNCTIONS = {}

FUNCTIONS["count_rows_where"] = types.FunctionDeclaration(
    name="count_rows_where",
    description="Count the number of rows matching some filter criterion using SQL. The SQL query will be SELECT COUNT(*) FROM {table_name} WHERE {column_name} {filter_condition};",
    parameters={
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
            "column_name": {"type": "string"},
            "filter_condition": {"type": "string"}
        },
        "required": ["table_name", "column_name", "filter_condition"]
    },
)

FUNCTIONS["sample_values"] = types.FunctionDeclaration(
    name="sample_values",
    description="Sample a number of values from a column in a table.",
    parameters={
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
            "column_name": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["table_name", "column_name"]
    },
)

FUNCTIONS["run_sql"] = types.FunctionDeclaration(
    name="run_sql",
    description="Run an SQL query.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"}
        },
        "required": ["query"]
    },
)

FUNCTIONS["run_python"] = types.FunctionDeclaration(
    name="run_python",
    description="Runs Python code in an isolated temporary workspace with access to a preloaded Pandas DataFrame called df.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string"}
        },
        "required": ["code"]
    },
)

TOOL_MAP = {
    "count_rows_where": count_rows_where,
    "sample_values": sample_values,
    "run_sql": run_sql,
    "run_python": run_python,
}

PROFILES = {
    "free_sql": ["run_sql"],
    "free_python": ["run_python"],
    "specialized": ["count_rows_where", "sample_values"],
}

def build_tools(profile_name: str):
    if profile_name:
        function_declarations = [
            FUNCTIONS[name] for name in PROFILES[profile_name]
        ]

        return [
            types.Tool(function_declarations=function_declarations)
        ]
    else:
        return None
