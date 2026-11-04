import re

import sqlite3

from utils.table_description import generate_table_description


def get_tables(cursor):
    return set(row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ))

def check_ordering(cursor, col_name, table_name):
    result = cursor.execute(
        f"SELECT 1 FROM {table_name} GROUP BY {col_name} HAVING COUNT(*) > 1 LIMIT 1;"
    ).fetchone()
    return result is not None

def test_augmentation_validity(df, database_dir):
    df = df.copy()
    for i, row in df.iterrows():
        gold_sql = row["query"]
        augmented_sql = row["sql_augmentation"]
        db_id = row["db_id"]

        connection = sqlite3.connect(":memory:")
        disk_conn = sqlite3.connect(f"{database_dir}/{db_id}/{db_id}.sqlite")
        disk_conn.backup(connection)
        cursor = connection.cursor()

        try:
            tables_before = get_tables(cursor)

            try:
                cursor.execute(augmented_sql)
            except Exception as e:
                if "already exists" in str(e):
                    m = re.match(r"CREATE TABLE\s+([^\s(]+)", augmented_sql, re.I)
                    if m:
                        table = m.group(1)
                        new_sql = augmented_sql.replace(f"CREATE TABLE {table}",
                                                        f"CREATE TABLE {table}_augmented",
                                                        1)
                        try:
                            cursor.execute(new_sql)
                            augmented_sql = new_sql
                            df.at[i, "sql_augmentation"] = new_sql
                        except:
                            err_msg = f"Failed to execute augmentation: {e}"
                            print(f"{err_msg} \n db_id: {db_id} \n {augmented_sql}")
                            df.at[i, "valid"] = False
                            df.at[i, "error"] = err_msg
                            continue
                    else:
                        err_msg = f"Failed to execute augmentation: {e}"
                        print(f"{err_msg} \n db_id: {db_id} \n {augmented_sql}")
                        df.at[i, "valid"] = False
                        df.at[i, "error"] = err_msg
                        continue
                else:
                    err_msg = f"Failed to execute augmentation: {e}"
                    print(f"{err_msg} \n db_id: {db_id} \n {augmented_sql}")
                    df.at[i, "valid"] = False
                    df.at[i, "error"] = err_msg
                    continue

            tables_after = get_tables(cursor)
            new_tables = tables_after - tables_before

            if len(new_tables) != 1:
                err_msg = f"{len(new_tables)} new tables created. Needs to be 1."
                print(f"{err_msg} \n db_id: {db_id} \n {augmented_sql}")
                df.at[i, "valid"] = False
                df.at[i, "error"] = err_msg
                continue

            new_table_name = next(iter(new_tables))
            df.at[i, "new_table_name"] = new_table_name

            count = cursor.execute(f"SELECT COUNT(*) FROM {new_table_name};").fetchone()[0]

            if count == 0:
                err_msg = "created empty table."
                print(f"{err_msg} \n db_id: {db_id} \n {augmented_sql}")
                df.at[i, "valid"] = False
                df.at[i, "error"] = err_msg
                continue

            pattern = r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            match = re.search(pattern, gold_sql, re.IGNORECASE)
            original_table_name = match.group(1)
            df.at[i, "table_name"] = original_table_name

            table_pattern = rf'\b{re.escape(original_table_name)}\b'

            updated_gold_sql = re.sub(
                table_pattern,
                new_table_name,
                gold_sql,
                flags=re.IGNORECASE
            )
            gold_answer = cursor.execute(gold_sql).fetchall()

            try:
                augmented_answer = cursor.execute(updated_gold_sql).fetchall()
            except Exception as e:
                if row["augmentation_method"] == "remove_column":
                    try:
                        new_descriptions = generate_table_description(cursor=cursor, table=new_table_name)
                        new_description = new_descriptions["detailed_description"]
                        new_small_description = new_descriptions["small_description"]
                        df.at[i, "valid"] = True
                        df.at[i, "new_table_description"] = new_description
                        df.at[i, "new_table_small_description"] = new_small_description
                    except Exception as e2:
                        err_msg = f"Failed to generate new table description: {e2}"
                        print(f"{err_msg} \n db_id: {db_id} \n {augmented_sql}")
                        df.at[i, "valid"] = False
                        df.at[i, "error"] = err_msg
                    continue
                else:
                    err_msg = f"Unable to execute answer from new SQL: {e}"
                    print(f"{err_msg} \n db_id: {db_id} \n Augmentation: {augmented_sql} \n Old gold: {gold_sql} \n New gold: {updated_gold_sql}")
                    df.at[i, "valid"] = False
                    df.at[i, "error"] = err_msg
                    continue

            if set(gold_answer) != set(augmented_answer):
                df.at[i, "valid"] = True
                new_descriptions = generate_table_description(
                    cursor=cursor, table=new_table_name
                )
                new_description = new_descriptions["detailed_description"]
                new_small_description = new_descriptions["small_description"]
                df.at[i, "new_table_description"] = new_description
                df.at[i, "new_table_small_description"] = new_small_description
            else:
                if "GROUP BY" in gold_sql.upper():
                    group_by_column = re.search(
                        r'GROUP\sBY\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                        gold_sql,
                        re.IGNORECASE
                    )
                    if group_by_column:
                        group_by_column = group_by_column.group(1)
                        order_ambiguity = check_ordering(cursor, group_by_column, new_table_name)
                        if order_ambiguity:
                            df.at[i, "valid"] = True

                err_msg = "New table gave same answer as old table."
                print(f"New table gave same answer as old table. \n db_id: {db_id} \n Gold sql: {gold_sql} \n Augmentation: {augmented_sql}")
                df.at[i, "valid"] = False
                df.at[i, "error"] = err_msg

        finally:
            connection.close()
            disk_conn.close()

    df["valid"] = df["valid"].astype(bool)
    return df
