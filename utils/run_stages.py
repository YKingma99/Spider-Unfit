import os
from pathlib import Path
import yaml

from dataset.prompts.extract_question_categories.extract_question_categories import get_categorization_template, question_prompt_mapping, get_categorization_template_simple, question_prompt_mapping_simple
from dataset.prompts.extract_augmentation_methods.extract_augmentation_methods import get_augmentation_template, augmentation_prompt_mapping
from dataset.prompts.self_iterate.validation import get_validation_template, validation_prompt_mapping
from dataset.prompts.schemas import QuestionCategoriesResult, AugmentationResult, UnanswerabilityResults, ValidationResult, QuestionCategoriesResultSimple
from models.baseline.prompts.answerability_detection import answerability_detection_prompt_mapping, get_answerability_detection_template
from utils.run_manager import RunManager
from utils.utils import build_input_instances, load_config
from utils.base_llm_provider import BaseLLMProvider
from utils.providers.google_provider import GoogleProvider
from utils.providers.openai_provider import OpenAIProvider


class StageConfig:
    def __init__(self, name, mapping, template_fn, output_struct):
        self.name = name
        self.mapping = mapping
        self.template_fn = template_fn
        self.output_struct = output_struct


CATEGORIZATION_STAGE = StageConfig(
    name="categorization",
    mapping=question_prompt_mapping,
    template_fn=get_categorization_template,
    output_struct=QuestionCategoriesResult
)

CATEGORIZATION_STAGE_SIMPLE = StageConfig(
    name="categorization",
    mapping=question_prompt_mapping_simple,
    template_fn=get_categorization_template_simple,
    output_struct=QuestionCategoriesResultSimple
)

AUGMENTATION_STAGE = StageConfig(
    name="augmentation",
    mapping=augmentation_prompt_mapping,
    template_fn=get_augmentation_template,
    output_struct=AugmentationResult
)

AUGMENTATION_STAGE_SIMPLE = StageConfig(
    name="augmentation",
    mapping=augmentation_prompt_mapping,
    template_fn=get_augmentation_template,
    output_struct=AugmentationResult
)

VALIDATION_STAGE = StageConfig(
    name="validation",
    mapping=validation_prompt_mapping,
    template_fn=get_validation_template,
    output_struct=ValidationResult
)

DETECTION_STAGE = StageConfig(
    name="detection",
    mapping=answerability_detection_prompt_mapping,
    template_fn=get_answerability_detection_template,
    output_struct=UnanswerabilityResults
)

def init_run(base_dir, config_path, run_id=None, run_type="generic"):
    if run_id:
        if not os.path.isdir(base_dir / run_id):
            raise ValueError(f"run_id: {run_id} not valid!")
        metadata_path = Path(base_dir / run_id / "meta")
        config = load_config((metadata_path / "used_config.yaml"))
        client = BaseLLMProvider(config=config)
        run_manager = RunManager(
            client=client,
            working_dir=None,
            metadata_path=(metadata_path / "metadata.json"),
            run_type=run_type
        )
    else:
        config = load_config(config_path)
        client = BaseLLMProvider(config=config)
        run_manager = RunManager(client=client, working_dir=base_dir, run_type=run_type)
        run_dir = run_manager.get_run_dir()
        with open(f"{run_dir}/meta/used_config.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)
    return client, config, run_manager

def run_stage(run_manager, df, client, stage_config: StageConfig):
    name = stage_config.name
    if name in run_manager.metadata["stages"]:
        status = run_manager.metadata["stages"][name]["status"]
    else:
        if isinstance(client.provider, OpenAIProvider):
            input_instances = build_input_instances(provider="openai",df=df, mapping=stage_config.mapping)
        elif isinstance(client.provider, GoogleProvider):
            input_instances = build_input_instances(provider="gemini",df=df, mapping=stage_config.mapping)
        else:
            raise ValueError(f"Unknown provider: {type(client.provider)}")
        stage_dir = run_manager.init_stage(name)
        prompt_template = stage_config.template_fn()

        batch_info = client.generate_batch(
            prompt=prompt_template,
            input_instances=input_instances,
            batch_dir=stage_dir,
            output_struct=stage_config.output_struct
        )

        run_manager.register_stage(name, batch_info=batch_info)
        print(f"Started stage: {name}. run_id: {run_manager.metadata["run_id"]}")
        return None

    if status.lower() in {"submitted", "validating", "in_progress", "failed", "job_state_pending", "job_state_running"}:
        output_path = run_manager.retrieve_batch(name)
    elif status.lower() in {"completed", "job_state_succeeded"}:
        output_path = run_manager.metadata["stages"][name]["output_path"]
    else:
        raise ValueError(f"Unknown batch status: {status}")
    return output_path
