from collections import defaultdict
import json

import pandas as pd
import sqlite3

from utils.table_description import generate_table_description, get_row_count


def load_schemas(tables_json_path):
    with open(tables_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    schemas = {}
    for db in data:
        schemas[db["db_id"]] = db
    return schemas

def extract_table_ids(obj):
    table_ids = set()

    if isinstance(obj, dict):
        if "from" in obj:
            for unit in obj["from"].get("table_units", []):
                unit_type, value = unit

                if unit_type == "table_unit":
                    table_ids.add(value)

                elif unit_type == "sql":
                    table_ids.update(extract_table_ids(value))

        for key in ["except", "union", "intersect"]:
            if obj.get(key) is not None:
                table_ids.update(extract_table_ids(obj[key]))

        for v in obj.values():
            table_ids.update(extract_table_ids(v))

    elif isinstance(obj, list):
        for item in obj:
            table_ids.update(extract_table_ids(item))

    return table_ids

def get_single_table_id(sql_obj):
    table_ids = extract_table_ids(sql_obj)
    if len(table_ids) == 1:
        return next(iter(table_ids))
    return None

def add_table_description(row, table_description_cache):
    table_id = (row["db_id"], row["table_id"])
    return table_description_cache[table_id]

def load_spider_dataset(config) -> pd.DataFrame:
    spider_dir = "raw_data/spider_data/spider_data"
    df = pd.read_json(f"{spider_dir}/test.json")    
    df["table_id"] = df["sql"].apply(get_single_table_id)
    df = df.dropna(subset=["table_id"])
    df["table_id"] = df["table_id"].astype(int)
    df = df[:config["n_samples"]]
    unique_tables = set(zip(df["db_id"], df["table_id"]))

    schemas = load_schemas("raw_data/spider_data/spider_data/test_tables.json")

    row_count_cache = {}
    valid_tables = set()

    tables_by_db = defaultdict(list)
    for db_id, table_id in unique_tables:
        tables_by_db[db_id].append(table_id)

    for db_id, table_ids in tables_by_db.items():
        connection = sqlite3.connect(f"{spider_dir}/test_database/{db_id}/{db_id}.sqlite")
        cursor = connection.cursor()
        schema = schemas[db_id]

        for table_id in table_ids:
            table_name = schema["table_names_original"][table_id]
            row_count = get_row_count(cursor, table_name)

            row_count_cache[(db_id, table_id)] = row_count

            if row_count > 0:
                valid_tables.add((db_id, table_id))

        connection.close()
    valid_table_set = set(valid_tables)
    df = df[df.set_index(["db_id", "table_id"]).index.isin(valid_table_set)]

    table_description_cache = {}
    table_small_description_cache = {}

    for db_id, table_id in valid_tables:
        table_name = schemas[db_id]["table_names_original"][table_id]
        connection = sqlite3.connect(
            f"{spider_dir}/test_database/{db_id}/{db_id}.sqlite"
        )
        cursor = connection.cursor()
        descriptions = generate_table_description(
            cursor=cursor, table=table_name
        )
        description = descriptions["detailed_description"]
        small_description = descriptions["small_description"]
        table_description_cache[(db_id, table_id)] = description
        table_small_description_cache[(db_id, table_id)] = small_description
        connection.close()

    df["table_description"] = df.apply(
        lambda row: add_table_description(row, table_description_cache),
        axis=1
    )
    df["small_table_description"] = df.apply(
        lambda row: add_table_description(row, table_small_description_cache),
        axis=1
    )

    df["custom_id"] = [f"spider_{i}" for i in range(len(df))]
    return df
