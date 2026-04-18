from typing import Optional
from pydantic import BaseModel, Field
from ..enums import TableType
from .column import Column


class ForeignKey(BaseModel):
    column_name: str
    ref_schema: str
    ref_table: str
    ref_column: str


class Index(BaseModel):
    index_name: str
    is_unique: bool
    is_primary_key: bool
    columns: list[str] = Field(default_factory=list)


class Table(BaseModel):
    schema_name: str
    table_name: str
    columns: list[Column] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKey] = Field(default_factory=list)
    indexes: list[Index] = Field(default_factory=list)
    description: Optional[str] = None
    classification: Optional[TableType] = None
