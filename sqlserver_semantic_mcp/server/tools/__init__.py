from . import (
    metadata, policy, query, cache,
    relationship, object_tool, semantic,
)  # noqa: F401


def register_all() -> None:
    metadata.register()
    policy.register()
    query.register()
    cache.register()
    relationship.register()
    object_tool.register()
    semantic.register()
