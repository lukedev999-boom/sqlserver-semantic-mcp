from pydantic import BaseModel, Field


class PolicyOperations(BaseModel):
    select:   bool = True
    insert:   bool = False
    update:   bool = False
    delete:   bool = False
    truncate: bool = False
    create:   bool = False
    alter:    bool = False
    drop:     bool = False
    execute:  bool = False
    merge:    bool = False


class PolicyConstraints(BaseModel):
    require_where_for_update: bool = True
    require_where_for_delete: bool = True
    require_top_for_select:   bool = False
    max_rows_returned:        int  = Field(default=1000, ge=1)
    max_rows_affected:        int  = Field(default=100, ge=1)
    allow_multi_statement:    bool = False
    query_timeout_seconds:    int  = Field(default=30, ge=1)


class PolicyScope(BaseModel):
    allowed_databases: list[str] = Field(default_factory=list)
    allowed_schemas:   list[str] = Field(default_factory=list)
    allowed_tables:    list[str] = Field(default_factory=list)
    denied_tables:     list[str] = Field(default_factory=list)


class PolicyProfile(BaseModel):
    profile_name: str
    operations:   PolicyOperations  = Field(default_factory=PolicyOperations)
    constraints:  PolicyConstraints = Field(default_factory=PolicyConstraints)
    scope:        PolicyScope       = Field(default_factory=PolicyScope)


class PolicyFile(BaseModel):
    active_profile: str = "readonly"
    profiles: dict[str, PolicyProfile]
