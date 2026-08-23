from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings

settings = get_settings()

# Confirmed live (first real Postgres round-trip): LangGraph's serializer
# warns "Deserializing unregistered type ... This will be blocked in a
# future version" for every custom type `AgentState` actually stores —
# `Citation` (pydantic), `EntityType` (enum), and the `ProvenancedRelationEdge`/
# `CommunityWithEmbedding` NamedTuples. It still works today, but silently
# would not after a LangGraph upgrade — explicitly allowlisting these now
# is the fix the warning itself points at, not something to leave for
# "later."
_serde = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("app.schemas.query", "Citation"),
        ("app.services.ontology", "EntityType"),
        ("app.services.graph_store", "ProvenancedRelationEdge"),
        ("app.services.graph_store", "CommunityWithEmbedding"),
    ]
)

# PostgresSaver requires autocommit + prepare_threshold=0 + a dict row
# factory on every connection it uses — confirmed by reading
# `PostgresSaver.from_conn_string`'s own source (it opens a single
# connection with exactly these kwargs). Applying the same kwargs to a real
# `ConnectionPool` instead of one connection is what makes this safe for
# concurrent `/query` requests — the same reasoning `app/core/db.py`'s
# SQLAlchemy engine already uses, just for LangGraph's own checkpoint
# tables instead of the application's own schema.
#
# `open=False`: never connects at import time (mirrors SQLAlchemy's
# `create_engine`, which is also lazy) — opened explicitly from
# `app.main`'s lifespan instead, so importing this module in a test or
# script that doesn't need Postgres can't accidentally try to reach it.
_pool = ConnectionPool(
    settings.database_url,
    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    min_size=1,
    max_size=10,
    open=False,
)

checkpointer = PostgresSaver(_pool, serde=_serde)


def open_checkpointer() -> None:
    """Opens the pool and creates LangGraph's own checkpoint tables if they
    don't already exist. `setup()` is idempotent (`CREATE TABLE IF NOT
    EXISTS` under the hood) — safe to call on every app startup, not just
    the first one; this project's own schema still goes through Alembic
    (`alembic/versions/`), this is purely LangGraph's separate,
    self-managed checkpoint schema.
    """
    _pool.open()
    checkpointer.setup()


def close_checkpointer() -> None:
    _pool.close()


def delete_conversation(conversation_id: str) -> None:
    """Explicit "forget this conversation" — permanently removes every
    checkpoint for this thread. There's deliberately no *automatic*
    retention/TTL policy here — LangGraph's checkpoint tables carry no
    last-activity timestamp of their own, so a real one needs this
    project's own bookkeeping (a small `conversations` table tracking
    `last_active_at`) feeding a periodic cleanup job (LangGraph's own
    `checkpointer.prune(thread_ids, strategy="keep_latest")` is the right
    primitive for that once such a table exists) — documented as known
    follow-up work in docs/phase-5-agentic-loop.md rather than built now.
    """
    checkpointer.delete_thread(conversation_id)
