import argparse
from pathlib import Path

from dataset.dataset_loaders import load_spider_dataset
from dataset.prompts.schemas import CATEGORY_TO_METHODS, AUGMENTATION_METHOD_DESCRIPTIONS, QuestionCategoriesResult, AugmentationResult, CATEGORY_TO_LABEL, ValidationResult, CATEGORY_INSTRUCTIONS, QuestionCategoriesResultSimple
from scripts.augmentation_testing import test_augmentation_validity
from utils.run_stages import run_stage, CATEGORIZATION_STAGE, AUGMENTATION_STAGE, init_run, StageConfig, VALIDATION_STAGE, CATEGORIZATION_STAGE_SIMPLE
from utils.utils import load_jsonl, load_stage_df, save_stage_df


def balance_labels(df):
    return df

def build_methods_prompt(methods):
    return "\n".join(
        f"- {m.value}: {AUGMENTATION_METHOD_DESCRIPTIONS[m]}"
        for m in methods
    )

def process_categorization_output(df, batch_output):
    df = df.merge(batch_output, on="custom_id", how="left")
    df = df.rename(columns={"custom_id": "original_id"})

    print(df.columns)

    df = df.explode("categories")
    before = len(df)
    df_nan = df[df["categories"].isna()]
    df = df.dropna(subset=["categories"])
    removed = before-len(df)
    print(f"Removed {removed} samples due to no categories.")
    df["category_idx"] = df.groupby("original_id").cumcount()

    df["custom_id"] = (
        df["original_id"] + "_cat_" + df["category_idx"].astype(str)
    )
    return df, df_nan

def main(dataset_name: str, run_id: str=None, simple: bool=False):
    working_dir = Path(f"processed_data/{dataset_name}/intermediate_steps")

    client, config, run_manager = init_run(
        working_dir, config_path=Path("config.yaml"), run_id=run_id, run_type="dataset_pipeline"
    )

    if dataset_name.lower() == "spider":
        df = load_spider_dataset(config)
    else:
        raise ValueError(f"Unsupported dataset: {dataset_name}")

    stage = "categorization"
    categorized_df = load_stage_df(run_manager, stage)
    if categorized_df is not None:
        print("Loaded categorized_df")
    else:
        if not simple:
            categorization_output_path = run_stage(
                run_manager, df, client, CATEGORIZATION_STAGE
            )
            if categorization_output_path is None:
                return
            else:
                batch_output = load_jsonl(config["llm"]["provider"], categorization_output_path, schema=QuestionCategoriesResult)
                categorized_df, df_nan = process_categorization_output(df, batch_output)
                df_nan.to_pickle("answerable_examples.pkl")
                save_stage_df(run_manager, stage, categorized_df)
                print("Fetched categorized_df")
        elif simple:
            categorization_output_path = run_stage(
                run_manager, df, client, CATEGORIZATION_STAGE_SIMPLE
            )
            if categorization_output_path is None:
                return
            else:
                batch_output = load_jsonl(config["llm"]["provider"], categorization_output_path, schema=QuestionCategoriesResultSimple)
                categorized_df, df_nan = process_categorization_output(df, batch_output)
                df_nan.to_pickle("answerable_examples_simple.pkl")
                save_stage_df(run_manager, stage, categorized_df)
                print("Fetched categorized_df")
        else:
            raise ValueError

    stage = "augmentation"
    augmented_df = load_stage_df(run_manager, stage)
    if augmented_df is not None:
        print("Loaded augmented_df")
    else:
        categorized_df["label"] = categorized_df["categories"].map(CATEGORY_TO_LABEL)
        categorized_df = balance_labels(categorized_df)
        categorized_df["instructions"] = categorized_df["categories"].map(CATEGORY_INSTRUCTIONS)
        categorized_df["augmentation_methods"] = categorized_df["categories"].map(CATEGORY_TO_METHODS)
        categorized_df["augmentation_methods"] = categorized_df["augmentation_methods"].apply(build_methods_prompt)

        augmentation_output_path = run_stage(
            run_manager, categorized_df, client, AUGMENTATION_STAGE
        )

        if augmentation_output_path is None:
            return
        else:
            batch_output = load_jsonl(config["llm"]["provider"], augmentation_output_path, schema=AugmentationResult)
            augmented_df = categorized_df.merge(batch_output, on="custom_id")
            save_stage_df(run_manager, stage, augmented_df)
            print("Fetched augmented_df")

    validated_df = test_augmentation_validity(
        augmented_df, "raw_data/spider_data/spider_data/test_database"
    )

    max_iters = config["augmentation_iteration_max"]
    for i in range(max_iters):
        print(f"i: {i}")
        stage = f"validation_{i}"
        loaded_df = load_stage_df(run_manager, stage)
        if loaded_df is not None:
            print(f"Loaded {stage}")
            validated_df = loaded_df
            continue

        invalid_df = validated_df.loc[~validated_df["valid"]]
        if invalid_df.empty:
            print("No invalid augmentations.")
            break

        iteration_stage = StageConfig(
            name=stage,
            mapping=VALIDATION_STAGE.mapping,
            template_fn=VALIDATION_STAGE.template_fn,
            output_struct=VALIDATION_STAGE.output_struct
        )

        iterated_output_path = run_stage(
            run_manager, invalid_df, client, iteration_stage
        )

        if iterated_output_path is None:
            return

        batch_output = load_jsonl(config["llm"]["provider"], iterated_output_path, schema = ValidationResult)
        validated_df[f"sql_augmentation_iter_{i}"] = validated_df["sql_augmentation"]
        validated_df = validated_df.set_index("custom_id")
        batch_output = batch_output.set_index("custom_id")

        validated_df = validated_df[~validated_df.index.duplicated(keep="first")] 

        for col in batch_output.columns:
            validated_df.loc[batch_output.index, col] = batch_output[col]

        validated_df = validated_df.reset_index()
        validated_df = test_augmentation_validity(validated_df, "raw_data/spider_data/spider_data/test_database")
        save_stage_df(run_manager, stage, validated_df)

    validated_df.to_pickle(f"processed_data/{dataset_name}/final/spider_simple.pkl")
    print(f"Number of rows: {validated_df.shape[0]}")
    print(f"Number of valid rows: {validated_df["valid"].sum()}")
    cleaned_df = validated_df.loc[validated_df["valid"]]
    cleaned_df.to_pickle(f"processed_data/{dataset_name}/final/spider_final_simple.pkl")
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g., spider)")
    parser.add_argument("--run_id", required=False, help="Optional run_id for resuming runs.")
    parser.add_argument("--simple", action="store_true", help="Optional argument, present run generation with less fine-grained instructions")
    args = parser.parse_args()

    main(args.dataset, args.run_id, args.simple)
