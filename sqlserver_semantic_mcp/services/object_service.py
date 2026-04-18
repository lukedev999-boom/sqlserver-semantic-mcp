import logging
from typing import Optional

from ..config import Config, get_config
from ..infrastructure.cache.semantic import (
    get_object_definition, upsert_object_definition,
)
from ..infrastructure.cache.structural import read_schema_version
from ..infrastructure.connection import fetch_one, fetch_all
from ..infrastructure.queries.object_queries import (
    GET_OBJECT_DEFINITION, GET_OBJECT_DEPENDENCIES,
)

logger = logging.getLogger(__name__)


async def describe_object(
    schema: str, object_name: str, object_type: str,
    cfg: Optional[Config] = None,
) -> dict:
    cfg = cfg or get_config()
    db = cfg.mssql_database
    ver = await read_schema_version(cfg.cache_path, db)
    object_hash = ver["object_hash"] if ver else ""

    cached = await get_object_definition(
        cfg.cache_path, db, schema, object_name, object_type,
    )
    if cached and cached["status"] == "ready" \
            and cached.get("object_hash") == object_hash:
        return cached

    qualified = f"{schema}.{object_name}"
    try:
        def_row = fetch_one(cfg, GET_OBJECT_DEFINITION, (qualified,))
        definition = def_row[0] if def_row and def_row[0] else None
        dep_rows = fetch_all(cfg, GET_OBJECT_DEPENDENCIES, (qualified,))
        dependencies = [f"{r[0]}.{r[1]}" for r in dep_rows if r[0]]
        affected = [
            f"{r[0]}.{r[1]}" for r in dep_rows
            if r[2] and "TABLE" in str(r[2]).upper()
        ]
        await upsert_object_definition(
            cfg.cache_path, db, schema, object_name, object_type,
            object_hash=object_hash, status="ready",
            definition=definition, dependencies=dependencies,
            affected_tables=affected,
        )
        return await get_object_definition(
            cfg.cache_path, db, schema, object_name, object_type,
        )
    except Exception as e:
        logger.exception("describe_object failed")
        await upsert_object_definition(
            cfg.cache_path, db, schema, object_name, object_type,
            object_hash=object_hash, status="error",
            error_message=str(e),
        )
        return {"status": "error", "error_message": str(e)}


async def trace_dependencies(
    schema: str, object_name: str, object_type: str,
    cfg: Optional[Config] = None,
) -> list[str]:
    obj = await describe_object(schema, object_name, object_type, cfg)
    return obj.get("dependencies", []) if obj else []
