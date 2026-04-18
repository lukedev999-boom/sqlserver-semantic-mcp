from typing import Optional
from pydantic import BaseModel, Field
from ..enums import ObjectType


class DbObject(BaseModel):
    schema_name: str
    object_name: str
    object_type: ObjectType
    definition: Optional[str] = None
    dependencies: list[str] = Field(default_factory=list)
    affected_tables: list[str] = Field(default_factory=list)
    description: Optional[str] = None
