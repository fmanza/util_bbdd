# Configuración del pool de conexiones
from sqlalchemy import create_engine

target_engine = create_engine(
    "postgresql+psycopg2://...",
    pool_size=4,  # conexiones persistentes
    max_overflow=2,  # conexiones extras si es necesario
)
# Capacidad total: 4 + 2 = 6 conexiones
