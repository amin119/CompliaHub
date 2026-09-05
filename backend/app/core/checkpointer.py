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

# Tracks whether *this process* has ever called `open_checkpointer()` —
# `psycopg_pool.ConnectionPool` can never be reopened once closed
# (`PoolClosed`, confirmed live in Phase 5 Part 2), so `ensure_open()` below
# must never blindly retry opening a pool some other code path already
# closed. This is a one-way latch, not a "is the pool currently usable"
# check: after `close_checkpointer()` runs, `_opened` stays `True` (opening
# again would crash) and any later attempt to actually use the checkpointer
# fails with its own, more localized error at the point of use, not here.
_opened = False


def open_checkpointer() -> None:
    """Opens the pool and creates LangGraph's own checkpoint tables if they
    don't already exist. `setup()` is idempotent (`CREATE TABLE IF NOT
    EXISTS` under the hood) — safe to call on every app startup, not just
    the first one; this project's own schema still goes through Alembic
    (`alembic/versions/`), this is purely LangGraph's separate,
    self-managed checkpoint schema.
    """
    global _opened
    _pool.open()
    checkpointer.setup()
    _opened = True


def ensure_open() -> None:
    """For callers that need the checkpointer usable but don't themselves
    own its lifecycle the way `app.main`'s lifespan (or a test's own
    open/close fixture) does — e.g. Phase 7's eval harness Celery task,
    which runs in a worker process with no FastAPI lifespan of its own and
    must open the pool exactly once, lazily, before its first real use. A
    no-op if `open_checkpointer()` already ran anywhere in this process
    (including by `app.main`'s lifespan itself, where this is always a
    no-op — the pool is already open by the time any request arrives).
    """
    if not _opened:
        open_checkpointer()


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
