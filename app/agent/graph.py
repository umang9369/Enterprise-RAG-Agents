import logfire
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.nodes.planner import planner_node
from app.agents.nodes.responder import generate_node
from app.agents.nodes.retriever import retrieve_node
from app.agents.state import AgentState
from app.config import settings

def create_checkpointer() -> BaseCheckpointSaver:
    """
    Create a durable Postgres checkpointer for production.
    Falls back to in-memory MemorySaver only if Postgres is unreachable.

    Note: we run setup() through a single autocommit connection because
    LangGraph's migrations include CREATE INDEX CONCURRENTLY, which Neon
    rejects when run inside a transaction (the default ConnectionPool mode).
    """

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            conninfo=settings.postgres_uri,
            max_size=20,
            open=False,
            timeout=10,
            num_workers=3,
            check=ConnectionPool.check_connection,
            max_idle=240,
        )
        # Verify connectivity before committing to Postgres; otherwise the first
        # graph invocation will hang on connection retries.
        pool.open()
        conn = pool.getconn()
        pool.putconn(conn)

        # Run migrations on a separate autocommit connection so that
        # CREATE INDEX CONCURRENTLY succeeds on Neon.
        try:
            with PostgresSaver.from_conn_string(settings.postgres_uri) as setup_saver:
                setup_saver.setup()
        except Exception as e:
            logfire.warning(f"⚠️ Postgres checkpointer setup failed ({e}); falling back to MemorySaver.")
            pool.close()
            return MemorySaver()

        checkpointer = PostgresSaver(pool)
        logfire.info("🗄️ Postgres checkpointer configured.")
        return checkpointer
    except Exception as e:
        logfire.warning(
            f"⚠️ Postgres checkpointer unavailable ({e}); falling back to MemorySaver. "
            "Do not use MemorySaver in production — state is lost on restart."
        )
        return MemorySaver()
