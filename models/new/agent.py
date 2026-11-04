import argparse

from models.new.table_environment import TableEnvironment
from utils.utils import load_config, load_prompt
from dataset.prompts.schemas import UnanswerabilityResults, UnanswerabilityResultsBlind
from models.new.tools import build_tools, TOOL_MAP
from dataset.prompts.schemas import UNANSWERABILITY_LABELS, UNANSWERABILITY_LABELS_BLIND
from utils.base_llm_provider import BaseLLMProvider
from models.new.configurations import CONFIG_BY_NAME

import pandas as pd
from pathlib import Path
import json
from enum import Enum
from pydantic import BaseModel


class AbstentionLabels(str, Enum):
    missing_value = "missing_value"
    missing_column = "missing_column"
    epistemically_invalid = "epistemically_invalid"
    insufficient_granularity = "insufficient_granularity"
    empty_answer = "empty_answer"
    other_abstention = "other_abstention"
    answer = "answer"
    external_knowledge = "external_knowledge"

ABSTENTION_LABEL_DESCRIPTIONS = {
    AbstentionLabels.missing_value: "The question wasn't answered because the asked for value(s) don't exist in the data.",
    AbstentionLabels.missing_column: "The question wasn't answered because a required column is not in the data.",
    AbstentionLabels.epistemically_invalid: "The question is wasn't answered because there is not enough statistical basis to answer the question.",
    AbstentionLabels.insufficient_granularity: "The question wasn't answered because the granularity of the data is too coarse.",
    AbstentionLabels.empty_answer: "The question was answered and the answer was that the answer set is empty or requested count is 0.",
    AbstentionLabels.external_knowledge: "The system has recognized a limitation in the data and used external knowledge to answer the question.",
    AbstentionLabels.other_abstention: "The question wasn't answered due to some other reason.",
    AbstentionLabels.answer: "The question was answered.",
}

ABSTENTION_LABELS = "\n".join(
    f"- {cat.value}: {desc}"
    for cat, desc in ABSTENTION_LABEL_DESCRIPTIONS.items()
)

class AbstentionResults(BaseModel):
    reasoning: str
    abstention_label: list[AbstentionLabels]

mapping_decision = {
    "question": "question",
    "description_small": "new_table_small_description",
}

mapping_tooling = {
    "question": "question",
    "description_small": "new_table_small_description",
}

mapping_reasoning = {
    "question": "question",
}

def build_prompt(instruction_folder: str, level: str, row, mapping, **kwargs):
    prompt_dir = Path(__file__).parent / "prompts" / instruction_folder / level /"placeholder"

    instruction = load_prompt(prompt_dir, "instruction.md")
    user_template = load_prompt(prompt_dir, "input.md")

    values = {
        placeholder: row[column]
        for placeholder, column in mapping.items()
    }

    values.update(kwargs)

    user_input = user_template.format(**values)

    return f"{instruction}\n\n{user_input}"

def format_tool_result(result):
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=False)

    return str(result)

def run_pre_step(client, row, instruction_folder):
    prompt = build_prompt(
        instruction_folder=instruction_folder, level="pre_reasoning", row=row, mapping=mapping_reasoning
    )
    response = client.generate(prompt)
    return response.text, response.usage_metadata.total_token_count

def run_tooling_step(
        client, max_steps, instruction_folder, row, history, tools, profile_name
    ):
    if profile_name == "free_python":
        tool_description = """
When using the run_python tool, the following code is already provided, so only write operations on the pandas dataframe `df`:

import pandas as pd
df = pd.read_pickle("{df_path}")
"""
    elif profile_name == "free_sql":
        tool_description = """
Use run_sql to execute SQL queries against the database.
"""
    elif profile_name == "specialized":
        tool_description = """
Use count_rows_where to count rows satisfying a condition without writing SQL yourself.
The SQL query will be SELECT COUNT(*) FROM {table_name} WHERE {column_name} {filter_condition};

Use sample_values to inspect representative values from a column.
The SQL query will be SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit};
"""
    else:
        raise ValueError(f"Unknown profile_name: {profile_name}")
    tool_tokens = 0
    environment = TableEnvironment(row)
    cursor, df = environment.connect()
    steps = 0
    final_text = None
    max_steps=1
    while steps < max_steps:
        prompt = build_prompt(instruction_folder=instruction_folder, level="tooling", row=row, mapping=mapping_tooling, history="\n".join(map(str, history)), unanswerability_categories=UNANSWERABILITY_LABELS, tool_description=tool_description)
        response = client.generate(prompt, tools=tools)
        tool_tokens += response.usage_metadata.total_token_count
        parts = response.candidates[0].content.parts

        if any(part.function_call is not None for part in parts):
            for part in parts:
                fc = part.function_call
                tool_args = dict(fc.args)

                if fc.name == "run_python":
                    tool_args.update({
                        "source_data_dir": environment.data_source_dir,
                        "df": df
                    })
                
                elif fc.name in {"count_rows_where", "sample_values", "run_sql"}:
                    tool_args.update({
                        "cursor": cursor
                    })
                
                else:
                    raise ValueError(f"Unknown function name: {fc.name}")
                tool_result = TOOL_MAP[fc.name](**tool_args)

                history.append(f"At step {steps} you called tool {fc.name} with arguments {fc.args} and got this result:")
                history.append(format_tool_result(tool_result))
            steps += 1
            continue
        
        final_text = response.text
        history.append(final_text)
        break

    if instruction_folder == "abstention" and final_text is None:
        prompt = build_prompt(
            instruction_folder=instruction_folder,
            level="answer",
            row=row,
            mapping=mapping_tooling,
            history="\n".join(map(str, history)),
            unanswerability_categories=UNANSWERABILITY_LABELS,
            tool_description=tool_description
        )

        response = client.generate(prompt)
        tool_tokens += response.usage_metadata.total_token_count

        final_text = response.text
        history.append(final_text)

    print("Steps used: ", steps)
    return history, tool_tokens, steps

def run_decision_step(client, row, instruction_folder, history):
    prompt = build_prompt(
        instruction_folder=instruction_folder, level="decision", row=row, mapping=mapping_decision, history="\n".join(map(str, history)), unanswerability_categories=UNANSWERABILITY_LABELS
    )
    final_response = client.generate(
        prompt, response_format=UnanswerabilityResults
    )
    return final_response, final_response.usage_metadata.total_token_count

def run_decision_step_blind(client, row, instruction_folder, history):
    prompt = build_prompt(
        instruction_folder=instruction_folder, level="decision", row=row, mapping=mapping_decision, history="\n".join(map(str, history)), unanswerability_categories=UNANSWERABILITY_LABELS_BLIND
    )
    final_response = client.generate(
        prompt, response_format=UnanswerabilityResultsBlind
    )
    return final_response, final_response.usage_metadata.total_token_count

def run_decision_step_abstention(client, row, instruction_folder, history):
    prompt = build_prompt(
        instruction_folder=instruction_folder, level="decision", row=row, mapping=mapping_decision, answer=history[-1], abstention_categories=ABSTENTION_LABELS
    )
    final_response = client.generate(prompt, response_format=AbstentionResults)
    return final_response, final_response.usage_metadata.total_token_count

def answerability_agent(exp_config, config, client, row):
    steps=0
    history = []
    tokens_used = 0
    max_steps = config["agent_max_steps"]
    tools = build_tools(exp_config.profile)
    for step in exp_config.workflow:
        if step == "pre_step":
            response, tokens1 = run_pre_step(
                client, row, exp_config.instruction_folder
            )
            tokens_used += tokens1
            history.append(response)
        elif step == "tooling":
            response, tokens2, steps = run_tooling_step(
                client, max_steps, exp_config.instruction_folder, row, history, tools, exp_config.profile
            )
            tokens_used += tokens2
            history = response
        elif step == "decision":
            response, tokens3 = run_decision_step(
                client, row, exp_config.instruction_folder, history
            )
            tokens_used += tokens3
            return response, history, tokens_used, steps
        elif step == "decision_blind":
            response, tokens4 = run_decision_step_blind(
                client, row, exp_config.instruction_folder, history
            )
            tokens_used += tokens4
            return response, history, tokens_used, steps
        elif step == "decision_abstention":
            response, tokens5 = run_decision_step_abstention(
                client, row, exp_config.instruction_folder, history
            )
            tokens_used += tokens5
            return response, history, tokens_used, steps
        else:
            raise ValueError(f"Unknown step in workflow: {step}")
    raise RuntimeError("Unexpectedly didn't exit during the workflow loop.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configuration", required=True, help="Configuration name"
    )
    args = parser.parse_args()

    config = load_config(Path("config.yaml"))
    exp_config = CONFIG_BY_NAME[args.configuration]
    if exp_config.llm:
        config["llm"]["google"]["model"] = exp_config.llm
        config["llm"]["openai"]["model"] = exp_config.llm
    client = BaseLLMProvider(config=config)
    df = pd.read_csv("processed_data/final/combined.csv")
    df = df[:config["n_samples"]]
    fails = 0
    max_retries = 3
    df["history"] = None
    df["answer"] = None
    for i, row in df.iterrows():
        if i % 25 == 0:
            print(f"Currently at sample {i} of {len(df)}")

        failed = False
        if row["label"] == "answerable":
            row["new_table_small_description"] = row["small_table_description"]

        for attempt in range(max_retries):
            try:
                result = answerability_agent(exp_config, config, client, row)
                labeled_response, history, tokens_used, steps = result
                df.at[i, "tokens_used"] = tokens_used
                df.at[i, "steps"] = steps
                if len(history) > 0:
                    df.at[i, "history"] = history
                    df.at[i, "answer"] = history[-1]
                print("real label: ", row["label"])
                try:
                    parsed_response = UnanswerabilityResults.model_validate_json(labeled_response.text)
                except Exception as e:
                    try:
                        parsed_response = UnanswerabilityResultsBlind.model_validate_json(labeled_response.text)
                    except Exception as ex:
                        try:
                            parsed_response = AbstentionResults.model_validate_json(labeled_response.text)
                        except Exception as exc:
                            raise ValueError(f"Failed to parse response: {labeled_response.text}: {e} {ex} {exc}")
                try:
                    print("Labels given by LLM: ", parsed_response.unanswerability_label)
                    df.at[i, "labeled_response"] = parsed_response.unanswerability_label
                    df.at[i, "label_reasoning"] = parsed_response.reasoning
                    failed = False
                    break
                except Exception as e:
                    print("Labels given by LLM: ", parsed_response.abstention_label)
                    df.at[i, "labeled_response"] = parsed_response.abstention_label
                    df.at[i, "label_reasoning"] = parsed_response.reasoning
                    failed = False
                    break
            except Exception as e:
                print(f"{i} failed for the {attempt + 1} time: {e}")
                failed = True
                df.at[i, "labeled_response"] = ["failed"]
                df.at[i, "label_reasoning"] = e

        if failed:
            fails += 1
    df.to_pickle(f"models/new/results/result_{args.configuration}.pkl")
    print(f"fails: {fails}")
    print("that's all folks")
