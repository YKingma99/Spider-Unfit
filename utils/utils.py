import json
from pathlib import Path
import yaml

from openbatch import PromptTemplateInputInstance
import pandas as pd

from dataset.prompts.schemas import PromptMapping


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        if path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(f)
        elif path.suffix == ".json":
            return json.load(f)
        else:
            raise ValueError(f"Unsupported config format: {path}")

def load_prompt(base_file, filename):
    return (Path(base_file).parent / filename).read_text(encoding="utf-8")

def build_input_instances(provider, df, mapping):
    if provider.lower() == "openai":
        return build_openai_input_instances(df, mapping)
    elif provider.lower() == "gemini":
        return build_gemini_input_instances(df, mapping)
    else:
        raise ValueError

def build_openai_input_instances(df, mapping: PromptMapping):
    return [
        PromptTemplateInputInstance(
            id=row.custom_id,
            prompt_value_mapping=mapping.build(row)
        )
        for row in df.itertuples()
    ]

def build_gemini_input_instances(df, mapping):
    return [
        {
            "key": row.custom_id,
            "prompt_value_mapping": mapping.build(row)
        }
        for row in df.itertuples()
    ]

def load_jsonl(provider, path, schema=None):
    if provider == "openai":
        return load_jsonl_openai(path, schema=schema)
    elif provider in {"gemini", "google"}:
        return load_jsonl_gemini(path, schema=schema)
    else:
        raise ValueError(f"Unknown provider: {provider}")

def load_jsonl_openai(path, schema=None):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            custom_id = obj.get("custom_id")
            content = obj["response"]["body"]["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            if schema:
                columns = schema(**parsed)
                row = {"custom_id": custom_id, **columns.model_dump()}
                records.append(row)
            else:
                row = {"custom_id": custom_id, **parsed}
                records.append(row)

    return pd.DataFrame(records)

def load_jsonl_gemini(path, schema=None):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            obj = json.loads(line)
            custom_id = obj.get("key")
            try:
                content = obj["response"]["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(content)

                if schema:
                    columns = schema(**parsed)
                    row = {"custom_id": custom_id, **columns.model_dump()}
                else:
                    row = {"custom_id": custom_id, **parsed}
            except Exception as e:
                print(f"Failed to load jsonl line: {line_num}: {e}")
                row = {"custom_id": custom_id, "failed": True, "error": str(e)}
            records.append(row)

    return pd.DataFrame(records)    

def save_stage_df(run_manager, stage, df):
    path = run_manager.get_stage_dir(stage) / f"{stage}.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)

def load_stage_df(run_manager, stage):
    path = run_manager.get_stage_dir(stage) / f"{stage}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    return None

def remove_defs_and_refs(schema: dict):
    schema = schema.copy()
    defs = schema.pop('$defs', {})

    def resolve(subschema):
        if isinstance(subschema, dict):
            ref = subschema.get('$ref', None)
            if ref:
                _def = ref.split('/')[-1]
                return resolve(defs[_def])
            return {
                _def: resolve(_ref)
                for _def, _ref in subschema.items()
            }
        if isinstance(subschema, list):
            return [resolve(ss) for ss in subschema]
        return subschema
    
    return resolve(schema)
