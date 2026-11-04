from openbatch import PromptTemplate, Message

from dataset.prompts.schemas import PromptMapping
from utils.utils import load_prompt


augmentation_prompt_mapping = PromptMapping(
    field_map={"question": "question",
               "categories": "categories",
               "instructions": "instructions",
               "table_description": "table_description",
               "augmentation_methods": "augmentation_methods"}
)

def get_augmentation_template():
    instructions = load_prompt(__file__, "instruction.md")
    user_input = load_prompt(__file__, "input.md")

    return PromptTemplate(messages=[
        Message(role="system", content=instructions),
        Message(role="user", content=user_input)
    ])
