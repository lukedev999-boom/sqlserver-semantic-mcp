from enum import Enum


class TableType(str, Enum):
    FACT = "fact"
    DIMENSION = "dimension"
    LOOKUP = "lookup"
    TRANSACTION = "transaction"
    BRIDGE = "bridge"
    CONFIG = "config"
    AUDIT = "audit"
    UNKNOWN = "unknown"


class ObjectType(str, Enum):
    VIEW = "VIEW"
    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"


class CacheStatus(str, Enum):
    PENDING = "pending"
    COMPUTING = "computing"
    READY = "ready"
    DIRTY = "dirty"
    ERROR = "error"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SqlOperation(str, Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    TRUNCATE = "TRUNCATE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    EXECUTE = "EXECUTE"
    EXEC = "EXEC"
    MERGE = "MERGE"
    UNKNOWN = "UNKNOWN"
