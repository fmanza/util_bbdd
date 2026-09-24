#!/usr/bin/env python3
"""
Script de Benchmarking para el Módulo `dump` — util_bbdd

Propósito: Medir rendimiento actual de carga masiva de datos entre esquemas.

Escenarios:
  1. Baseline: Configuración default (chunk_size=5000, no parallelismo)
  2. Optimizado: chunk_size dinámico, constraints batched, row counting desactivado
  3. Paralelo: parallel_pk_ranges=CPU_COUNT

Uso:
    python scripts/bench_dump.py --config baseline --volume small
    python scripts/bench_dump.py --config optimized --volume large --output bench_results/
    python scripts/bench_dump.py --list-configs
"""

from __future__ import annotations

import argparse
import json
import logging
import time

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

_log = logging.getLogger(__name__)


# ============================================================================
# Configuración de Logging
# ============================================================================


def setup_logging(verbose: bool = False) -> None:
    """Configura logging para benchmarks."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=level,
    )


# ============================================================================
# Configuraciones de Benchmark
# ============================================================================

BENCH_CONFIGS: dict[str, dict[str, Any]] = {
    "baseline": {
        "description": "Configuración default (chunk_size=5000, no paralelismo)",
        "dump_config": {
            "chunk_size": 5000,
            "parallel_pk_ranges": 1,
            "collect_row_counts": True,
            "bulk_audit_path": None,
        },
        "pre_load": {},
        "post_load": {},
    },
    "optimized": {
        "description": "Optimizado: chunk dinámico, constraints batched, row_counts=False",
        "dump_config": {
            "chunk_size": None,  # Dinámico (a calcular)
            "parallel_pk_ranges": 1,
            "collect_row_counts": False,
            "bulk_audit_path": None,
        },
        "pre_load": {},
        "post_load": {},
    },
    "parallel": {
        "description": "Paralelo: parallel_pk_ranges=CPU_COUNT, chunk_size=10000",
        "dump_config": {
            "chunk_size": 10000,
            "parallel_pk_ranges": None,  # Usar CPU_COUNT
            "collect_row_counts": False,
            "bulk_audit_path": None,
        },
        "pre_load": {},
        "post_load": {},
    },
}

# "tables": {nombre de tabla: filas}. Sin anotar, mypy infería Collection[str] al mezclar texto y diccionario.
BENCH_VOLUMES: dict[str, dict[str, Any]] = {
    "small": {
        "description": "Pequeño: 10k-50k filas",
        "tables": {
            "customers": 10000,
            "orders": 25000,
            "order_items": 50000,
        },
    },
    "medium": {
        "description": "Mediano: 100k-500k filas",
        "tables": {
            "customers": 100000,
            "orders": 250000,
            "order_items": 500000,
        },
    },
    "large": {
        "description": "Grande: 500k-2M filas",
        "tables": {
            "customers": 500000,
            "orders": 1000000,
            "order_items": 2000000,
        },
    },
}


# ============================================================================
# Generador de Datos de Prueba
# ============================================================================


class BenchDataGenerator:
    """Genera tablas de prueba para benchmarking."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_schema(self, schema_name: str) -> None:
        """Crea schema destino."""
        with self.engine.connect() as conn:
            try:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                conn.commit()
            except Exception as e:
                _log.warning(f"No se pudo crear schema {schema_name}: {e}")

    def create_tables(self, schema_name: str, volume_config: dict) -> None:
        """Crea tablas de origen con datos sintéticos."""
        with self.engine.connect() as conn:
            # Tabla customers
            conn.execute(
                text(f"""
                DROP TABLE IF EXISTS {schema_name}.customers
            """)
            )
            conn.execute(
                text(f"""
                CREATE TABLE {schema_name}.customers (
                    customer_id INTEGER PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    country VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.commit()

            # Tabla orders
            conn.execute(
                text(f"""
                DROP TABLE IF EXISTS {schema_name}.orders
            """)
            )
            conn.execute(
                text(f"""
                CREATE TABLE {schema_name}.orders (
                    order_id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_amount DECIMAL(10, 2),
                    FOREIGN KEY (customer_id) REFERENCES {schema_name}.customers(customer_id)
                )
            """)
            )
            conn.commit()

            # Tabla order_items
            conn.execute(
                text(f"""
                DROP TABLE IF EXISTS {schema_name}.order_items
            """)
            )
            conn.execute(
                text(f"""
                CREATE TABLE {schema_name}.order_items (
                    item_id INTEGER PRIMARY KEY,
                    order_id INTEGER NOT NULL,
                    product_name VARCHAR(100),
                    quantity INTEGER,
                    unit_price DECIMAL(10, 2),
                    FOREIGN KEY (order_id) REFERENCES {schema_name}.orders(order_id)
                )
            """)
            )
            conn.commit()

    def populate_tables(self, schema_name: str, volume_config: dict) -> None:
        """Inserta datos sintéticos en las tablas."""
        _log.info(f"Poblando {schema_name} con {volume_config} filas...")

        # Insert customers
        num_customers = volume_config.get("customers", 10000)
        with self.engine.connect() as conn:
            for i in range(0, num_customers, 1000):
                values = ",".join(
                    f"({j}, 'Customer {j}', 'cust{j}@example.com', 'Country{j % 50}')"
                    for j in range(i, min(i + 1000, num_customers))
                )
                conn.execute(
                    text(f"""
                    INSERT INTO {schema_name}.customers (customer_id, name, email, country)
                    VALUES {values}
                """)
                )
            conn.commit()

        # Insert orders
        num_orders = volume_config.get("orders", 25000)
        with self.engine.connect() as conn:
            for i in range(0, num_orders, 1000):
                values = ",".join(
                    f"({j}, {j % num_customers + 1}, CURRENT_TIMESTAMP, {j * 10.5})"
                    for j in range(i, min(i + 1000, num_orders))
                )
                conn.execute(
                    text(f"""
                    INSERT INTO {schema_name}.orders (order_id, customer_id, order_date, total_amount)
                    VALUES {values}
                """)
                )
            conn.commit()

        # Insert order_items
        num_items = volume_config.get("order_items", 50000)
        with self.engine.connect() as conn:
            for i in range(0, num_items, 1000):
                values = ",".join(
                    f"({j}, {j % num_orders + 1}, 'Product {j}', {j % 100 + 1}, {j * 0.99})"
                    for j in range(i, min(i + 1000, num_items))
                )
                conn.execute(
                    text(f"""
                    INSERT INTO {schema_name}.order_items (item_id, order_id, product_name, quantity, unit_price)
                    VALUES {values}
                """)
                )
            conn.commit()

        _log.info(f"Población completada: {num_customers} clientes, {num_orders} pedidos, {num_items} items")


# ============================================================================
# Benchmarking
# ============================================================================


class DumpBenchmark:
    """Ejecuta benchmark de carga masiva de datos."""

    def __init__(self, database_url: str, output_dir: Path | None = None) -> None:
        self.database_url = database_url
        self.output_dir = output_dir or Path("bench_results")
        self.engine = create_engine(database_url, poolclass=NullPool)
        self.results: list[dict[str, Any]] = []

    def run(
        self,
        config_name: str,
        volume_name: str,
        num_iterations: int = 1,
    ) -> dict[str, Any]:
        """Ejecuta benchmark con configuración y volumen especificado."""

        if config_name not in BENCH_CONFIGS:
            raise ValueError(f"Configuración desconocida: {config_name}")
        if volume_name not in BENCH_VOLUMES:
            raise ValueError(f"Volumen desconocido: {volume_name}")

        config = BENCH_CONFIGS[config_name]
        volume = BENCH_VOLUMES[volume_name]

        _log.info(f"Iniciando benchmark: config={config_name}, volume={volume_name}, iterations={num_iterations}")

        # Preparar datos
        gen = BenchDataGenerator(self.engine)
        source_schema = "bench_source"
        target_schema = "bench_target"

        gen.create_schema(source_schema)
        gen.create_schema(target_schema)
        gen.create_tables(source_schema, volume["tables"])
        gen.populate_tables(source_schema, volume["tables"])

        # Ejecutar carga (simulado sin util_bbdd.dump disponible)
        times: list[float] = []
        for iteration in range(num_iterations):
            _log.info(f"Iteración {iteration + 1}/{num_iterations}...")
            start = time.time()

            # TODO: Reemplazar con llamada real a DumpOrchestrator
            # result = DumpOrchestrator(dump_config).run()
            # Por ahora: simular lectura/escritura
            self._simulate_dump(source_schema, target_schema, config)

            elapsed = time.time() - start
            times.append(elapsed)
            _log.info(f"  Tiempo: {elapsed:.2f}s")

        # Calcular estadísticas
        result = {
            "timestamp": datetime.now().isoformat(),
            "config": config_name,
            "volume": volume_name,
            "iterations": num_iterations,
            "times_seconds": times,
            "min": min(times),
            "max": max(times),
            "avg": sum(times) / len(times),
            "total_rows": sum(volume["tables"].values()),
            "throughput_rows_per_sec": sum(volume["tables"].values()) / (sum(times) / len(times)),
        }

        self.results.append(result)
        return result

    def _simulate_dump(self, source_schema: str, target_schema: str, config: dict) -> None:
        """Simula lectura/escritura (sin util_bbdd.dump real)."""
        # Lectura origen
        with self.engine.connect() as conn:
            tables = ["customers", "orders", "order_items"]
            for table in tables:
                df = pd.read_sql(
                    f"SELECT * FROM {source_schema}.{table}",
                    conn,
                    chunksize=config["dump_config"]["chunk_size"] or 5000,
                )
                # Escritura destino
                for chunk in df:
                    chunk.to_sql(
                        table,
                        conn,
                        schema=target_schema,
                        if_exists="append",
                        index=False,
                    )

    def save_results(self) -> Path:
        """Guarda resultados en JSON."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.output_dir / f"bench_results_{timestamp}.json"

        with open(result_file, "w") as f:
            json.dump(self.results, f, indent=2)

        _log.info(f"Resultados guardados en: {result_file}")
        return result_file

    def print_summary(self) -> None:
        """Imprime resumen de resultados."""
        if not self.results:
            _log.info("No hay resultados para mostrar")
            return

        print("\n" + "=" * 80)
        print("BENCHMARK SUMMARY — Módulo `dump`")
        print("=" * 80)

        for result in self.results:
            print(f"\n{result['config'].upper()} — {result['volume'].upper()}")
            print(f"  Volumen: {result['total_rows']:,} filas")
            print(f"  Tiempo (avg): {result['avg']:.2f}s")
            print(f"  Throughput: {result['throughput_rows_per_sec']:,.0f} rows/sec")
            print(f"  Range: {result['min']:.2f}s - {result['max']:.2f}s")

        print("\n" + "=" * 80)


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Benchmark de rendimiento — Módulo dump (util_bbdd)",
    )
    parser.add_argument(
        "--config",
        choices=list(BENCH_CONFIGS.keys()),
        default="baseline",
        help="Configuración a benchmarkear",
    )
    parser.add_argument(
        "--volume",
        choices=list(BENCH_VOLUMES.keys()),
        default="small",
        help="Volumen de datos",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Número de iteraciones",
    )
    parser.add_argument(
        "--db-url",
        default="sqlite:///:memory:",
        help="URL de conexión a BD (defecto: SQLite in-memory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("bench_results"),
        help="Directorio de salida",
    )
    parser.add_argument(
        "--list-configs",
        action="store_true",
        help="Listar configuraciones disponibles",
    )
    parser.add_argument(
        "--list-volumes",
        action="store_true",
        help="Listar volúmenes disponibles",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if args.list_configs:
        print("\nConfiguraciones disponibles:")
        for name, cfg in BENCH_CONFIGS.items():
            print(f"  {name:15} — {cfg['description']}")
        return

    if args.list_volumes:
        print("\nVolúmenes disponibles:")
        for name, vol in BENCH_VOLUMES.items():
            print(f"  {name:15} — {vol['description']}")
        return

    bench = DumpBenchmark(args.db_url, args.output)
    bench.run(args.config, args.volume, args.iterations)

    bench.print_summary()
    bench.save_results()


if __name__ == "__main__":
    main()
