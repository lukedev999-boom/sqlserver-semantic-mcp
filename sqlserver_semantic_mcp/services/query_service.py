import logging
from typing import Optional

from ..config import Config, get_config
from ..infrastructure.connection import open_connection
from .policy_service import PolicyService

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(
        self,
        policy_service: PolicyService,
        cfg: Optional[Config] = None,
    ) -> None:
        self._policy = policy_service
        self._cfg = cfg or get_config()

    def validate(self, sql: str, database: str = "") -> dict:
        db = database or self._cfg.mssql_database
        return self._policy.validate(sql, database=db)

    def run_safe_query(
        self, sql: str, max_rows: Optional[int] = None,
    ) -> dict:
        policy = self._policy.current_policy()
        limit = max_rows or policy.constraints.max_rows_returned
        db = self._cfg.mssql_database

        validation = self._policy.validate(sql, database=db)
        if not validation["allowed"]:
            return {
                "executed": False,
                "validation": validation,
                "error": validation["reason"],
            }

        op = validation["intent"]["primary_operation"]

        try:
            with open_connection(self._cfg) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(sql)

                    if op == "SELECT":
                        columns = [d[0] for d in cursor.description]
                        # Fetch limit+1 to detect truncation precisely
                        rows = cursor.fetchmany(limit + 1)
                        truncated = len(rows) > limit
                        rows = rows[:limit]
                        return {
                            "executed": True,
                            "validation": validation,
                            "columns": columns,
                            "rows": [list(r) for r in rows],
                            "row_count": len(rows),
                            "truncated": truncated,
                        }

                    affected = cursor.rowcount
                    conn.commit()
                    cap = policy.constraints.max_rows_affected
                    return {
                        "executed": True,
                        "validation": validation,
                        "rows_affected": affected,
                        "exceeded_cap": affected > cap,
                    }
                finally:
                    try:
                        cursor.close()
                    except Exception:
                        logger.warning("Failed to close cursor", exc_info=True)
        except Exception as e:
            logger.exception("Query execution failed")
            return {
                "executed": False,
                "validation": validation,
                "error": str(e),
            }
