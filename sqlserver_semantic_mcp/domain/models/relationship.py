from pydantic import BaseModel


class Relationship(BaseModel):
    from_schema: str
    from_table: str
    to_schema: str
    to_table: str
    fk_column: str
    ref_column: str
    type: str  # "many_to_one" | "one_to_one" | "self_ref"
