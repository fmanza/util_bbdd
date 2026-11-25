# Configuración del pool del Engine de SQLAlchemy que recibe ParallelBulkLoader
from sqlalchemy import create_engine

target_engine = create_engine(
    "postgresql+psycopg://usr:pwd@host/db",  # psycopg 3
    pool_size=4,  # conexiones persistentes
    max_overflow=2,  # conexiones extra si hacen falta (QueuePool de SQLAlchemy)
)
# Capacidad total: 4 + 2 = 6 conexiones >= max_workers
