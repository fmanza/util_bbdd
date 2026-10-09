"""Verificador unificado de condiciones de ejecución por motor de base de datos.

Extiende el patrón ``MySQLVariableValidator`` a todos los motores soportados
y emite un informe consolidado en una única llamada al LOG.

Uso típico::

    from util_bbdd.connection import EngineReadinessAdvisor

    advisor = EngineReadinessAdvisor()
    # Una sola vez por engine en el proceso (lo que hace BulkCrud.__init__):
    advisor.report_once(engine)
    # Solo checks estáticos (sin conexión):
    advisor.report("postgresql", conn_params)
    # Checks estáticos + dinámicos (con conexión activa):
    with engine.connect() as conn:
        advisor.report("postgresql", conn_params, connection=conn)
"""

from __future__ import annotations

import logging
import threading
import weakref

from typing import TYPE_CHECKING, Any, ClassVar

from ._advisory import AdvisoryFinding

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger: logging.Logger = logging.getLogger(__name__)

_LEVEL_ORDER: dict[str, int] = {"OK": 0, "INFO": 1, "WARNING": 2, "CRITICAL": 3}
_LEVEL_ICONS: dict[str, str] = {"OK": "✅  OK  ", "INFO": "ℹ️  INFO", "WARNING": "⚠️  WARN", "CRITICAL": "🔴  CRIT"}


class EngineReadinessAdvisor:
    """Verifica y reporta las condiciones de ejecución de un motor de BD.

    Soporta: postgresql, mariadb, mysql, oracle, mssql/sqlserver, sqlite.
    Para mariadb/mysql delega en ``MySQLVariableValidator`` (checks dinámicos)
    y añade checks estáticos de pool config.

    El método ``report()`` emite **una única** llamada al logger con el bloque
    completo de hallazgos y recomendaciones. ``report_once()`` lo hace una sola vez
    por ``Engine`` en el proceso: ``BulkCrud`` se instancia muchas veces sobre el mismo
    engine (una por partición en ``ParallelBulkLoader``, una por hilo en ``dump``).
    """

    # Engines ya verificados por report_once(); referencias débiles para no retenerlos.
    _reported_engines: ClassVar[weakref.WeakSet[Engine]] = weakref.WeakSet()
    _reported_lock: ClassVar[threading.Lock] = threading.Lock()

    #: Checks estáticos de MariaDB/MySQL con mínimo: (parámetro, mínimo, unidad, recomendación si queda por debajo).
    _MYSQL_MINIMUMS: ClassVar[tuple[tuple[str, int, str, str], ...]] = (
        ("pool_size", 5, "", "Mínimo 5 para cargas concurrentes"),
        ("write_timeout", 30, "s", "Recomendado ≥60 s en cargas masivas para evitar 'Lost connection'"),
        ("read_timeout", 30, "s", "Recomendado ≥30 s"),
    )

    def check(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        connection: Any = None,
    ) -> list[AdvisoryFinding]:
        """Ejecuta todos los checks disponibles y retorna los hallazgos.

        Args:
            db_type: Dialecto SQLAlchemy (``postgresql``, ``mysql``, ``mariadb``,
                     ``oracle``, ``mssql``, ``sqlite``).
            conn_params: Parámetros de conexión/pool (ya saneados).
            connection: Conexión SQLAlchemy activa para checks dinámicos (opcional).

        Returns:
            Lista de hallazgos ordenados por severidad descendente.
        """
        engine = db_type.lower().strip()
        findings: list[AdvisoryFinding] = []

        try:
            if engine in {"mysql", "mariadb"}:
                findings.extend(self._check_mysql(conn_params, connection=connection))
            elif engine == "postgresql":
                findings.extend(self._check_postgresql(conn_params, connection=connection))
            elif engine in {"mssql", "sqlserver"}:
                findings.extend(self._check_sqlserver(conn_params, connection=connection))
            elif engine == "oracle":
                findings.extend(self._check_oracle(conn_params, connection=connection))
            elif engine == "sqlite":
                findings.extend(self._check_sqlite(conn_params, connection=connection))
            else:
                logger.debug(f"EngineReadinessAdvisor: motor '{db_type}' sin checks específicos")
        except Exception as exc:
            logger.debug(f"EngineReadinessAdvisor: error en checks para '{db_type}': {exc}")

        findings.sort(key=lambda f: _LEVEL_ORDER.get(f.level, 0), reverse=True)
        return findings

    def report(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        connection: Any = None,
    ) -> None:
        """Emite el informe de condiciones de ejecución en una única llamada al logger.

        El nivel de log es ``warning`` si hay WARNING o CRITICAL, ``info`` en caso contrario.

        Args:
            db_type: Dialecto SQLAlchemy.
            conn_params: Parámetros de conexión/pool.
            connection: Conexión activa para checks dinámicos (opcional).
        """
        findings = self.check(db_type, conn_params, connection=connection)
        if not findings:
            return

        host: str = str(conn_params.get("host", ""))
        port: str = str(conn_params.get("port", ""))
        host_str: str = f"{host}:{port}" if host else ""

        header = f"  ENGINE READINESS REPORT  ·  {db_type}"
        if host_str:
            header = f"{header}  ·  {host_str}"

        width = max(60, len(header) + 4)
        border = "═" * width

        lines: list[str] = [f"╔{border}╗", f"║{header.center(width)}║", f"╚{border}╝"]

        for f in findings:
            icon = _LEVEL_ICONS.get(f.level, f.level)
            param_col = f"{f.param}={f.current}"[:38].ljust(40)
            rec = f"  → {f.recommendation}" if f.recommendation else ""
            lines.append(f"  [{icon}]  {param_col}{rec}")

        counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("CRITICAL", "WARNING", "INFO", "OK")}
        summary_parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        lines.append(f"{'─' * width}")
        lines.append(f"  Resumen: {' · '.join(summary_parts)}")

        worst_lvl = _LEVEL_ORDER.get(findings[0].level, 0) if findings else 0
        block = "\n".join(lines)

        if worst_lvl >= _LEVEL_ORDER["WARNING"]:
            logger.warning(block)
        else:
            logger.info(block)

    def report_once(self, engine: Engine) -> bool:
        """Verifica ``engine`` y emite su informe solo la primera vez que se pide en el proceso.

        Los parámetros se leen de ``engine.url`` y ``engine.pool``. Con conexión se ejecutan
        los checks estáticos y dinámicos; si no se puede conectar, solo los estáticos (sin reintento).

        Thread-safe: el engine se registra antes de verificarlo, de modo que los hilos
        concurrentes ni repiten la verificación ni esperan a que termine. La clave es el
        objeto ``Engine``, no su URL: dos engines al mismo servidor se verifican por separado
        (pueden tener pool distinto) y ``engine.dispose()`` no provoca una nueva verificación.
        ``report()`` explícito no está limitado.

        Args:
            engine: Engine SQLAlchemy síncrono.

        Returns:
            True si esta llamada hizo la verificación; False si el engine ya estaba verificado.
        """
        with self._reported_lock:
            if engine in self._reported_engines:
                return False
            self._reported_engines.add(engine)

        dialect = engine.dialect.name
        conn_params = self._conn_params_from_engine(engine)
        reported = False
        try:
            with engine.connect() as conn:
                self.report(dialect, conn_params, connection=conn)
                reported = True
        except Exception:
            # Sin conexión activa, solo checks estáticos; si ya se informó (falló el cierre), no se repite
            if not reported:
                try:
                    self.report(dialect, conn_params)
                except Exception as exc:
                    logger.debug(f"Error en verificación de motor '{dialect}': {exc}")
        return True

    @staticmethod
    def _conn_params_from_engine(engine: Engine) -> dict[str, Any]:
        """host/port/database de ``engine.url``, pool_size/max_overflow/pool_timeout del pool y, en mssql, el driver."""
        url = engine.url
        conn_params: dict[str, Any] = {}
        if url.host:
            conn_params["host"] = url.host
        if url.port:
            conn_params["port"] = url.port
        if url.database:
            conn_params["database"] = url.database

        # pool.size() es público en QueuePool pero no en la clase base Pool (sin type stub)
        pool = engine.pool
        try:
            _size_fn = getattr(pool, "size", None)
            if callable(_size_fn):
                conn_params["pool_size"] = _size_fn()
        except Exception:
            pass
        # Atributos privados de SA 2.x: si cambian, simplemente no se informan (D-05)
        for _attr, _key in (("_max_overflow", "max_overflow"), ("_timeout", "pool_timeout")):
            _val = getattr(pool, _attr, None)
            if _val is not None:
                conn_params[_key] = _val

        if engine.dialect.name == "mssql":
            conn_params["sql_server_driver"] = "pyodbc" if "pyodbc" in str(url.drivername).lower() else "pymssql"
        return conn_params

    # ─── Adaptadores por motor ────────────────────────────────────────────────

    def _check_mysql(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []

        # Checks estáticos de pool/config: solo los parámetros presentes. report_once() no conoce autocommit ni los
        # timeouts del driver (no están en engine.url) y un valor por defecto no debe presentarse como leído.
        if "autocommit" in conn_params:
            autocommit: bool = bool(conn_params["autocommit"])
            findings.append(
                AdvisoryFinding(
                    level="WARNING" if autocommit else "OK",
                    param="autocommit",
                    current=str(autocommit),
                    recommendation="autocommit=True confirma cada INSERT individualmente; usar transacciones para bulk"
                    if autocommit
                    else "",
                )
            )
        for param, minimum, unit, recommendation in self._MYSQL_MINIMUMS:
            if param in conn_params:
                findings.append(self._minimum_finding(param, int(conn_params[param]), minimum, unit, recommendation))

        pool_timeout: int = int(conn_params.get("pool_timeout", 30))
        if pool_timeout < 10:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_timeout",
                    current=f"{pool_timeout}s",
                    recommendation="Recomendado ≥10 s para evitar timeouts en picos de carga",
                )
            )

        # Checks dinámicos: delegar en MySQLVariableValidator existente
        if connection is not None:
            findings.extend(self._check_mysql_dynamic(connection))

        return findings

    @staticmethod
    def _minimum_finding(param: str, value: int, minimum: int, unit: str, recommendation: str) -> AdvisoryFinding:
        """WARNING con ``recommendation`` si ``value`` queda por debajo de ``minimum``; OK en otro caso."""
        if value < minimum:
            return AdvisoryFinding(
                level="WARNING", param=param, current=f"{value}{unit}", recommendation=recommendation
            )
        return AdvisoryFinding(level="OK", param=param, current=f"{value}{unit}", recommendation="")

    def _check_mysql_dynamic(self, connection: Any) -> list[AdvisoryFinding]:
        """Usa MySQLVariableValidator para leer variables del servidor."""
        findings: list[AdvisoryFinding] = []
        try:
            from .mariadb._config import MySQLOptimalConfig
            from .mariadb._variables import MySQLVariableValidator

            validator = MySQLVariableValidator(connection)
            current = validator.read_variables()
            if not current:
                return findings

            recommended = MySQLOptimalConfig.production()
            thresholds = {
                "innodb_buffer_pool_size": recommended.innodb_buffer_pool_size,
                "max_allowed_packet": recommended.max_allowed_packet,
            }

            for var, min_val in thresholds.items():
                actual = current.get(var)
                if actual is None:
                    continue
                actual_fmt = validator.format_bytes(actual)
                rec_fmt = validator.format_bytes(min_val)
                if actual < min_val:
                    findings.append(
                        AdvisoryFinding(
                            level="WARNING",
                            param=var,
                            current=actual_fmt,
                            recommendation=f"Recomendado ≥{rec_fmt}; "
                            f"SET GLOBAL {var} = {min_val}; (requiere SUPER o SYSTEM_VARIABLES_ADMIN)",
                        )
                    )
                else:
                    findings.append(AdvisoryFinding(level="OK", param=var, current=actual_fmt, recommendation=""))
        except Exception as exc:
            logger.debug(f"_check_mysql_dynamic: {type(exc).__name__}: {exc}")
        return findings

    def _check_postgresql(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .postgresql._variables import PostgreSQLVariableValidator

            v = PostgreSQLVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_postgresql: {type(exc).__name__}: {exc}")
            return []

    def _check_sqlserver(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .sqlserver._variables import SQLServerVariableValidator

            v = SQLServerVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_sqlserver: {type(exc).__name__}: {exc}")
            return []

    def _check_oracle(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .oracle._variables import OracleVariableValidator

            v = OracleVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_oracle: {type(exc).__name__}: {exc}")
            return []

    def _check_sqlite(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .sqlite._variables import SQLiteVariableValidator

            v = SQLiteVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_sqlite: {type(exc).__name__}: {exc}")
            return []


__all__: list[str] = ["AdvisoryFinding", "EngineReadinessAdvisor"]
