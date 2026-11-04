from openbatch import PromptTemplate, Message

from dataset.prompts.schemas import PromptMapping, QUESTION_CATEGORIES, ONLY_UNANSWERABILITY_LABELS
from utils.utils import load_prompt


question_prompt_mapping = PromptMapping(
    field_map={"question": "question", "query": "query"},
    static_values={"categories": QUESTION_CATEGORIES}
)

question_prompt_mapping_simple = PromptMapping(
    field_map={"question": "question", "query": "query"},
    static_values={"categories": ONLY_UNANSWERABILITY_LABELS}
)

def get_categorization_template():
    instructions = load_prompt(__file__, "instruction.md")
    user_input = load_prompt(__file__, "input.md")

    return PromptTemplate(messages=[
        Message(role="system", content=instructions),
        Message(role="user", content=user_input)
    ])

def get_categorization_template_simple():
    instructions = load_prompt(__file__, "instruction_simple.md")
    user_input = load_prompt(__file__, "input.md")

    return PromptTemplate(messages=[
        Message(role="system", content=instructions),
        Message(role="user", content=user_input)
    ])
