from dataclasses import dataclass

@dataclass
class Configuration:
    name: str
    instruction_folder: str
    profile: str
    llm: str

    def __post_init__(self):
        workflow = []

        if self.instruction_folder in {"with_checks", "without_checks", "without_tools"}:
            workflow.append("pre_step")

        if self.profile:
            workflow.append("tooling")

        if self.instruction_folder in {"with_checks", "without_checks", "without_tools"}:
            workflow.append("decision")
        elif self.instruction_folder == "without_categories":
            workflow.append("decision_blind")
        elif self.instruction_folder == "abstention":
            workflow.append("decision_abstention")
        else:
            workflow.append("decision")

        self.workflow = workflow

CONFIGS = [
    Configuration(
        name="sql_checks",
        instruction_folder="with_checks",
        profile="free_sql",
        llm=None
    ),
    Configuration(
        name="python_checks",
        instruction_folder="with_checks",
        profile="free_python",
        llm=None
    ),
    Configuration(
        name="specialized_checks",
        instruction_folder="with_checks",
        profile="specialized",
        llm=None
    ),
    Configuration(
        name="python_no_categories",
        instruction_folder="without_categories",
        profile="free_python",
        llm=None
    ),
    Configuration(
        name="python_no_checks",
        instruction_folder="without_checks",
        profile="free_python",
        llm=None
    ),
    Configuration(
        name="sql_no_checks",
        instruction_folder="without_checks",
        profile="free_sql",
        llm=None
    ),
    Configuration(
        name="abstention",
        instruction_folder="abstention",
        profile="free_python",
        llm=None
    ),
    Configuration(
        name="python_checks_small",
        instruction_folder="with_checks",
        profile="free_python",
        llm="gemini-3.1-flash-lite"
    ),
    Configuration(
        name="python_no_checks_small",
        instruction_folder="without_checks",
        profile="free_python",
        llm="gemini-3.1-flash-lite"
    )
]

CONFIG_BY_NAME = {config.name: config for config in CONFIGS}
