from dataclasses import asdict, dataclass, fields
from typing import ClassVar, Literal

from pydantic import BaseModel


@dataclass
class RequirementModel:
    __specmetrics_specification__: ClassVar[Literal["specification/v1"]] = (
        "specification/v1"
    )
    prompt: str


model = RequirementModel(prompt="must be concise")
assert [field.name for field in fields(RequirementModel)] == ["prompt"]
assert asdict(model) == {"prompt": "must be concise"}
assert model.__specmetrics_specification__ == "specification/v1"


class PydanticRequirementModel(BaseModel):
    __specmetrics_specification__: ClassVar[Literal["specification/v1"]] = (
        "specification/v1"
    )
    prompt: str


pydantic_model = PydanticRequirementModel(prompt="must be concise")
assert list(PydanticRequirementModel.model_fields) == ["prompt"]
assert pydantic_model.model_dump() == {"prompt": "must be concise"}
assert pydantic_model.__specmetrics_specification__ == "specification/v1"
