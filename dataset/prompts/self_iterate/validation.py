from openbatch import PromptTemplate, Message

from dataset.prompts.schemas import PromptMapping
from utils.utils import load_prompt


validation_prompt_mapping = PromptMapping(
    field_map={
        "sql_augmentation": "sql_augmentation",
        "error": "error",
        "table_description": "table_description",
        "augmentation_method": "augmentation_method"
    }
)

def get_validation_template():
    instructions = load_prompt(__file__, "instruction.md")
    user_input = load_prompt(__file__, "input.md")

    return PromptTemplate(messages=[
        Message(role="system", content=instructions),
        Message(role="user", content=user_input)
    ])
