from enum import Enum

from pydantic import BaseModel


class QuestionCategories(str, Enum):
    insufficient_location_coverage = "insufficient_location_coverage"
    insufficient_temporal_coverage = "insufficient_temporal_coverage"
    insufficient_entity_coverage = "insufficient_entity_coverage"
    insufficient_events_coverage = "insufficient_events_coverage"
    insufficient_location_granularity = "insufficient_location_granularity"
    insufficient_entity_granularity = "insufficient_entity_granularity"
    insufficient_events_granularity = "insufficient_events_granularity"
    insufficient_temporal_granularity = "insufficient_temporal_granularity"
    insufficient_measurement_granularity = "insufficient_measurement_granularity"
    missing_column = "missing_column"
    missing_value = "missing_value"


class AugmentationTypes(str, Enum):
    remove_column = "remove_column"
    remove_rows = "remove_rows"
    add_constant = "add_constant"
    bin_values = "bin_values"
    roll_up_values = "rollup_values"
    add_extreme_rows = "add_extreme_rows"
    change_to_extreme_value = "change_to_extreme_value"
    add_rows_one_class = "add_rows_one_class"
    remove_value = "remove_value"
    set_values_null = "set_values_null"


class QuestionCategoriesSimple(str, Enum):
    insufficient_granularity = "insufficient_granularity"
    missing_column = "missing_column"
    missing_value = "missing_value"


class QuestionReasoning(BaseModel):
    category: QuestionCategories
    explanation: str


class QuestionCategoriesResult(BaseModel):
    reasoning_cat: list[QuestionReasoning]
    categories: list[QuestionCategories]


class QuestionReasoningSimple(BaseModel):
    category: QuestionCategoriesSimple
    explanation: str


class QuestionCategoriesResultSimple(BaseModel):
    reasoning_cat: list[QuestionReasoningSimple]
    categories: list[QuestionCategoriesSimple]

class AugmentationResult(BaseModel):
    reasoning_augmentation: str
    augmentation_method: AugmentationTypes
    sql_augmentation: str


class PromptMapping:
    def __init__(self, field_map, static_values=None):
        self.field_map = field_map
        self.static_values = static_values or {}

    def build(self, row):
        return {
            **{k: getattr(row, v) for k, v in self.field_map.items()},
            **self.static_values
        }


CATEGORY_DESCRIPTIONS = {
    QuestionCategories.insufficient_location_coverage: "The dataset does not cover the geographic regions required by the question.",
    QuestionCategories.insufficient_temporal_coverage: "Dataset does not cover full time range required.",
    QuestionCategories.insufficient_entity_coverage: "The dataset does not adequately cover the entities or subpopulations required to answer the question. Explicitly exclude location from this category. Do not use this category for identifiers or identifying columns, such as names.",
    QuestionCategories.insufficient_events_coverage: "Dataset lacks data on categories of events",
    QuestionCategories.insufficient_location_granularity: "Geographic data is too coarse for the query. For example, the location name or location level (e.g. country/city) must be mentioned. Only asking \"Where?\" questions do NOT apply for this category.",
    QuestionCategories.insufficient_entity_granularity: "Entity attributes are too coarse or grouped at a higher level than required. Do not use this category for identifiers or identifying columns, such as names. The required granularity level must be mentioned in the question, for example by mentioning the required value which can be binned or rolled up (for example, a level of food item or type of engine). Do not use this category merely because an attribute could be grouped or generalized further. If the question can still be answered correctly after such grouping, this category does not apply. Negative example: \"How many products are there for each product type?\": Not insufficient_entity_granularity. Even if individual product types are merged into broader categories, the question does not require a finer product-type granularity.",
    QuestionCategories.insufficient_events_granularity: "Events lack required level of detail.  Do not use this category for identifiers or identifying columns, such as names. The required granularity level must be mentioned in the question, for example by mentioning the required value which can be binned or rolled up. This category does NOT apply if the question asks for types without specifying a granularity level.",
    QuestionCategories.insufficient_temporal_granularity: "Time data is too coarse for the question. The required granularity must be mentioned in the question. For example, the question specify the required time granularity (e.g., day, year, or time). Only asking \"date\" is not specific enough, so this category does not apply.",
    QuestionCategories.insufficient_measurement_granularity: "Numeric values are recorded at a coarser numerical precision or resolution than required to answer the question. This concerns measurements done using instruments or any numerical values that can be binned, but only if binning would change the meaning of the question.",
    QuestionCategories.missing_column: "The question requires a column which is not present in the data.",
    QuestionCategories.missing_value: "The specific value asked for is not in the data. These questions ask about single rows or cells.",
}

QUESTION_CATEGORIES = "\n".join(
    f"- {cat.value}: {desc}"
    for cat, desc in CATEGORY_DESCRIPTIONS.items()
)

CATEGORY_TO_METHODS = {
    QuestionCategories.insufficient_location_coverage: [
        AugmentationTypes.remove_rows
    ],
    QuestionCategories.insufficient_temporal_coverage: [
        AugmentationTypes.remove_rows
    ],
    QuestionCategories.insufficient_entity_coverage: [
        AugmentationTypes.remove_rows
    ],
    QuestionCategories.insufficient_events_coverage: [
        AugmentationTypes.remove_rows
    ],
    QuestionCategories.insufficient_location_granularity: [
        AugmentationTypes.bin_values,
        AugmentationTypes.roll_up_values
    ],
    QuestionCategories.insufficient_entity_granularity: [
        AugmentationTypes.bin_values
    ],
    QuestionCategories.insufficient_events_granularity: [
        AugmentationTypes.bin_values
    ],
    QuestionCategories.insufficient_temporal_granularity: [
        AugmentationTypes.bin_values,
        AugmentationTypes.roll_up_values
    ],
    QuestionCategories.insufficient_measurement_granularity: [
        AugmentationTypes.bin_values,
        AugmentationTypes.roll_up_values
    ],
    QuestionCategories.missing_column: [
        AugmentationTypes.remove_column
    ],
    QuestionCategories.missing_value: [
        AugmentationTypes.remove_value
    ],
    QuestionCategoriesSimple.missing_column: [
        AugmentationTypes.remove_column
    ],
    QuestionCategoriesSimple.missing_value: [
        AugmentationTypes.remove_value
    ],
    QuestionCategoriesSimple.insufficient_granularity: [
        AugmentationTypes.bin_values,
        AugmentationTypes.roll_up_values
    ]
}

AUGMENTATION_METHOD_DESCRIPTIONS = {
    AugmentationTypes.remove_column: "Remove relevant column(s) from the dataset.",
    AugmentationTypes.remove_rows: "Remove relevant rows from the dataset. Do not remove all rows.",
    AugmentationTypes.add_constant: "Add a constant to all values in a column.",
    AugmentationTypes.bin_values: "Create bins for values, preferrably more than 2 bins.",
    AugmentationTypes.roll_up_values: "Make the granularity more coarse using methods such as removing the day in the date or binning categorical values in broader categories.",
    AugmentationTypes.add_extreme_rows: "Add rows with extreme values to create high variance.",
    AugmentationTypes.change_to_extreme_value: "Change values in rows to extreme values to create high variance.",
    AugmentationTypes.add_rows_one_class: "Add rows for a class to make the data unbalanced.",
    AugmentationTypes.remove_value: "Remove the value the question asks for. A value is a single cell or row.",
    AugmentationTypes.set_values_null: "Set many values in a relevant column to NULL.",
}


CATEGORY_INSTRUCTIONS = {
    QuestionCategories.insufficient_location_coverage: "Do semantic filtering. Don't do arbitrary row deletion. Targeted rows must correspond to rows asked for in the question. Avoid targeting IDs unless the ID directly corresponds to the target location. Avoid targeting years or other temporal columns unless the year directly corresponds to the target location.",
    QuestionCategories.insufficient_entity_coverage: "Do semantic filtering. Don't do arbitrary row deletion. Target rows corresponding to the target entity implied by the question. Avoid targeting IDs unless the ID directly corresponds to the target entity. Avoid targeting years or other temporal columns unless the year directly corresponds to the target entity.",
    QuestionCategories.insufficient_events_coverage: "Do semantic filtering. Don't do arbitrary row deletion. Targeted rows must correspond to rows asked for in the question. Avoid targeting IDs unless the ID directly corresponds to the target event. Avoid targeting years or other temporal columns unless the year directly corresponds to the target event.",
    QuestionCategories.insufficient_temporal_coverage: "Do semantic filtering. Don't do arbitrary row deletion. Targeted rows must correspond to rows asked for in the question. Avoid targeting IDs unless the ID directly corresponds to the target location.",
    QuestionCategories.insufficient_entity_granularity: "Do not group categories by the letters in their names. Do not group entities by their identifiers. Introduce a hierarchy and map the entities into higher classes.",
    QuestionCategories.insufficient_events_granularity: "",
    QuestionCategories.insufficient_location_granularity: "",
    QuestionCategories.insufficient_measurement_granularity: "",
    QuestionCategories.insufficient_temporal_granularity: "Replace temporal values with explicit interval labels corresponding to a more coarse granularity. For example: year 2007 --> 2001-2010; 21-05-1919 --> May 1919. If the question mentions a single time value, make sure that value is not at the beginning or end of the interval.",
    QuestionCategories.missing_value: "Don't do arbitrary row deletion. Targeted rows must correspond to rows asked for in the question.",
    QuestionCategories.missing_column: "Don't do arbitrary column deletion.",
    QuestionCategoriesSimple.missing_value: "",
    QuestionCategoriesSimple.missing_column: "",
    QuestionCategoriesSimple.insufficient_granularity: "",
}


class ValidationResult(BaseModel):
    explanation: str
    sql_augmentation: str


class UnanswerabilityLabels(str, Enum):
    missing_value = "missing_value"
    missing_column = "missing_column"
    epistemically_invalid = "epistemically_invalid"
    insufficient_granularity = "insufficient_granularity"
    answerable = "answerable"


class UnanswerabilityLabelsBlind(str, Enum):
    missing_value = "missing_value"
    missing_column = "missing_column"
    epistemically_invalid = "epistemically_invalid"
    insufficient_granularity = "insufficient_granularity"
    unknown_unanswerable = "unknown_unanswerable"
    answerable = "answerable"


class UnanswerabilityResultsBlind(BaseModel):
    reasoning: str
    unanswerability_label: list[UnanswerabilityLabelsBlind]


UNANSWERABILITY_LABEL_DESCRIPTIONS_BLIND = {
    UnanswerabilityLabelsBlind.missing_value: "",
    UnanswerabilityLabelsBlind.missing_column:"",
    UnanswerabilityLabelsBlind.epistemically_invalid: "",
    UnanswerabilityLabelsBlind.insufficient_granularity: "",
    UnanswerabilityLabelsBlind.unknown_unanswerable: "",
    UnanswerabilityLabelsBlind.answerable: "",
}

UNANSWERABILITY_LABELS_BLIND = "\n".join(
    f"- {cat.value}"
    for cat, _ in UNANSWERABILITY_LABEL_DESCRIPTIONS_BLIND.items()
)

CATEGORY_TO_LABEL = {
    QuestionCategories.insufficient_location_coverage: UnanswerabilityLabels.missing_value,
    QuestionCategories.insufficient_entity_coverage: UnanswerabilityLabels.missing_value,
    QuestionCategories.insufficient_events_coverage: UnanswerabilityLabels.missing_value,
    QuestionCategories.insufficient_temporal_coverage: UnanswerabilityLabels.missing_value,
    QuestionCategories.insufficient_entity_granularity: UnanswerabilityLabels.insufficient_granularity,
    QuestionCategories.insufficient_events_granularity: UnanswerabilityLabels.insufficient_granularity,
    QuestionCategories.insufficient_location_granularity: UnanswerabilityLabels.insufficient_granularity,
    QuestionCategories.insufficient_measurement_granularity: UnanswerabilityLabels.insufficient_granularity,
    QuestionCategories.insufficient_temporal_granularity: UnanswerabilityLabels.insufficient_granularity,
    QuestionCategories.missing_value: UnanswerabilityLabels.missing_value,
    QuestionCategories.missing_column: UnanswerabilityLabels.missing_column,
    QuestionCategoriesSimple.missing_value: UnanswerabilityLabels.missing_value,
    QuestionCategoriesSimple.missing_column: UnanswerabilityLabels.missing_column,
    QuestionCategoriesSimple.insufficient_granularity: UnanswerabilityLabels.insufficient_granularity,
}


class UnanswerabilityResults(BaseModel):
    reasoning: str
    unanswerability_label: list[UnanswerabilityLabels]


UNANSWERABILITY_LABEL_DESCRIPTIONS = {
    UnanswerabilityLabels.missing_value: "The question is unanswerable because value(s) asked for are not present in the data. When the question asks for a value count and the value is not present, the question is unanswerable. Even if the count is 0. Do not treat an empty result set as answerable.",
    UnanswerabilityLabels.missing_column: "The question is unanswerable because a required column is not present in the data.",
    UnanswerabilityLabels.epistemically_invalid: "The question is unanswerable because there is not enough statistical basis to answer the question.",
    UnanswerabilityLabels.insufficient_granularity: "The question is unanswerable because the granularity of the data is too coarse.",
    UnanswerabilityLabels.answerable: "The question is answerable given the data.",
}

UNANSWERABILITY_LABELS = "\n".join(
    f"- {cat.value}: {desc}"
    for cat, desc in UNANSWERABILITY_LABEL_DESCRIPTIONS.items()
)

ONLY_UNANSWERABILITY_LABELS = "\n".join(
    f"- {cat.value}: {desc}"
    for cat, desc in UNANSWERABILITY_LABEL_DESCRIPTIONS.items()
    if cat not in {
        UnanswerabilityLabels.epistemically_invalid,
        UnanswerabilityLabels.answerable,
    }
)
