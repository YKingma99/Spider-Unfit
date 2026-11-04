def get_columns_with_types(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [(row[1], row[2]) for row in cursor.fetchall()]

def is_numeric_type(col_type):
    col_type = col_type.upper()
    return any(t in col_type for t in ["INT", "REAL", "FLOAT", "NUM", "DEC"])

def is_date_type(col_type):
    col_type = col_type.lower()
    return any(t in col_type for t in ["date", "time", "year"])

def get_column_range(cursor, table_name, column):
    try:
        cursor.execute(f"SELECT MIN({column}), MAX({column}) FROM {table_name}")
        result = cursor.fetchone()
        return result
    except Exception as e:
        print("failed to get column range")
        print(f"SELECT MIN({column}), MAX({column}) FROM {table_name}")
        print(e)
        return (None, None)

def get_row_count(cursor, table_name):
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
    except Exception as e:
        print("failed to get row count")
        print(f"SELECT COUNT(*) FROM {table_name}")
        print(e)
        return None

def get_examples(cursor, table_name, col_name, limit=3):
    try:
        cursor.execute(f"SELECT DISTINCT {col_name} FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        values = [str(row[0]) for row in rows]
        cursor.execute(f"SELECT COUNT(DISTINCT {col_name}) FROM {table_name}")
        num_distinct = cursor.fetchone()[0]
        return num_distinct, ", ".join(values)
    except Exception as e:
        print("Failed to get examples")
        print(f"SELECT DISTINCT {col_name} FROM {table_name} LIMIT {limit}")
        print(f"SELECT COUNT(DISTINCT {col_name}) FROM {table_name}")
        print(e)
        return None, None

def generate_table_description(cursor, table):
    description = f"Table name: {table}.\n"

    row_count = get_row_count(cursor, table)
    if row_count is not None:
        description += f"Number of rows: {row_count}.\n"

    columns = get_columns_with_types(cursor, table)

    small_description = description

    for col_name, col_type in columns:
        text = f"Column name: {col_name} Type: {col_type}"
        description += text
        small_description += text

        if is_numeric_type(col_type):
            min_val, max_val = get_column_range(cursor, table, col_name)
            text = f". Range: {min_val} to {max_val}"
            description += text
            small_description += text
            _, examples = get_examples(cursor, table, col_name)
            description += f", example format: {examples}"

        elif is_date_type(col_type):
            min_val, max_val = get_column_range(cursor, table, col_name)
            text = f". Date range: {min_val} to {max_val}"
            description += text
            small_description += text
            _, examples = get_examples(cursor, table, col_name)
            description += f", example format: {examples} "

        else:
            num_distinct, distinct_values = get_examples(cursor, table, col_name, limit=20)
            text = f". Number of distinct values: {num_distinct}"
            description += text
            small_description += text
            description += f", example distinct values: {distinct_values}"

        description += ".\n"
        small_description += ".\n"

    return {"detailed_description": description,
            "small_description": small_description,
    }