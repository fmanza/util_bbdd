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

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from ._advisory import AdvisoryFinding, EngineReadinessReport
from .config import _to_bool, _to_int

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
    # Resultado de report_once() por engine (engine_report) y su señal de fin para los hilos que lo esperan.
    _reports: ClassVar[weakref.WeakKeyDictionary[Engine, EngineReadinessReport]] = weakref.WeakKeyDictionary()
    _report_done: ClassVar[weakref.WeakKeyDictionary[Engine, threading.Event]] = weakref.WeakKeyDictionary()

    #: Motores con checks específicos en :meth:`check`; el resto devuelve una lista vacía.
    SUPPORTED_DB_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"mysql", "mariadb", "postgresql", "mssql", "sqlserver", "oracle", "sqlite"}
    )

    #: Checks estáticos de MariaDB/MySQL con mínimo: (parámetro, mínimo, unidad, recomendación si queda por debajo).
    _MYSQL_MINIMUMS: ClassVar[tuple[tuple[str, int, str, str], ...]] = (
        ("pool_size", 5, "", "Mínimo 5 para cargas concurrentes"),
        # T-03: el texto decía «≥60 s» con mínimo 30 (45 s salía OK); se ajusta el texto, no el umbral del WARNING.
        ("write_timeout", 30, "s", "Mínimo 30 s; en cargas masivas largas, 60 s o más evita 'Lost connection'"),
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

    def assess(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        engine: Engine | None = None,
    ) -> EngineReadinessReport:
        """Ejecuta :meth:`check` y devuelve los hallazgos junto con las condiciones en que se obtuvieron.

        Los checks estáticos usan ``conn_params`` (la configuración del usuario, no la del pool de ``engine``, que
        puede tener los valores por defecto de SQLAlchemy). ``engine`` solo aporta la conexión de los checks
        dinámicos; si no se puede conectar, se hacen solo los estáticos y el motivo queda en ``error``.

        Args:
            db_type: Motor (``postgresql``, ``mysql``, ``mariadb``, ``oracle``, ``mssql``/``sqlserver``, ``sqlite``).
            conn_params: Parámetros de conexión/pool.
            engine: Engine SQLAlchemy síncrono para los checks dinámicos (opcional).

        Returns:
            El informe; ``supported=False`` si el motor no tiene checks.

        Example:
            >>> report = EngineReadinessAdvisor().assess("mysql", {"pool_size": 2})
            >>> [(f.level, f.param) for f in report.findings]
            [('WARNING', 'pool_size')]
        """
        checked_at = datetime.now(UTC)
        if db_type.lower().strip() not in self.SUPPORTED_DB_TYPES:
            return EngineReadinessReport(
                db_type=db_type, findings=(), checked_at=checked_at, dynamic=False, supported=False
            )
        if engine is None:
            findings = self.check(db_type, conn_params)
            return EngineReadinessReport(
                db_type=db_type,
                findings=tuple(findings),
                checked_at=checked_at,
                dynamic=False,
                supported=True,
                error="Sin engine: solo checks estáticos",
            )

        dynamic_findings: list[AdvisoryFinding] | None = None
        error: str | None = None
        try:
            with engine.connect() as conn:
                dynamic_findings = self.check(db_type, conn_params, connection=conn)
        except Exception as exc:
            # Si ya hay hallazgos dinámicos, falló el cierre: se conservan. El mensaje puede llevar la URL: solo el tipo.
            if dynamic_findings is None:
                error = f"Sin conexión para los checks dinámicos ({type(exc).__name__})"
            logger.debug(f"EngineReadinessAdvisor.assess: '{db_type}' sin conexión: {type(exc).__name__}")
        if dynamic_findings is not None:
            return EngineReadinessReport(
                db_type=db_type,
                findings=tuple(dynamic_findings),
                checked_at=checked_at,
                dynamic=True,
                supported=True,
            )
        return EngineReadinessReport(
            db_type=db_type,
            findings=tuple(self.check(db_type, conn_params)),
            checked_at=checked_at,
            dynamic=False,
            supported=True,
            error=error,
        )

    def report(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        connection: Any = None,
    ) -> list[AdvisoryFinding]:
        """Emite el informe de condiciones de ejecución en una única llamada al logger.

        El nivel de log es ``warning`` si hay WARNING o CRITICAL, ``info`` en caso contrario.

        Args:
            db_type: Dialecto SQLAlchemy.
            conn_params: Parámetros de conexión/pool.
            connection: Conexión activa para checks dinámicos (opcional).

        Returns:
            Los hallazgos informados (los de :meth:`check`); sin hallazgos no se escribe nada.
        """
        findings = self.check(db_type, conn_params, connection=connection)
        if not findings:
            return findings

        # Redactar credenciales para evitar filtración en logs
        redacted_params = {
            k: "***" if k in ("password", "passwd", "pwd", "secret") else v for k, v in conn_params.items()
        }
        host: str = str(redacted_params.get("host", ""))
        port: str = str(redacted_params.get("port", ""))
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
        return findings

    def report_once(self, engine: Engine) -> bool:
        """Verifica ``engine`` y emite su informe solo la primera vez que se pide en el proceso.

        Los parámetros se leen de ``engine.url`` y ``engine.pool``. Con conexión se ejecutan
        los checks estáticos y dinámicos; si no se puede conectar, solo los estáticos (sin reintento).
        El resultado se guarda por engine: :meth:`engine_report` lo devuelve sin volver a conectar.

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
            done = threading.Event()
            self._report_done[engine] = done

        try:
            self._verify_and_store(engine)
        finally:
            done.set()
        return True

    def engine_report(self, engine: Engine, *, timeout: float = 60.0) -> EngineReadinessReport:
        """Condiciones de ``engine`` verificadas en este proceso (las de :meth:`report_once`).

        Si el engine no se había verificado, lo verifica ahora (y lo informa una vez en el LOG, como
        :meth:`report_once`); si otro hilo lo está verificando, espera hasta ``timeout`` segundos. Nunca lanza: si no hay
        resultado, el informe lleva el motivo en ``error``.

        Args:
            engine: Engine SQLAlchemy síncrono.
            timeout: Segundos de espera si otro hilo está verificando el mismo engine.

        Returns:
            El informe guardado para ``engine``.

        Example:
            >>> crud = BulkCrud(engine)  # verifica el engine al crearse
            >>> EngineReadinessAdvisor().engine_report(engine).dynamic  # sin nueva conexión
            True
        """
        self.report_once(engine)
        with self._reported_lock:
            report = self._reports.get(engine)
            done = self._report_done.get(engine)
        if report is None and done is not None and done.wait(timeout):
            with self._reported_lock:
                report = self._reports.get(engine)
        if report is not None:
            return report
        dialect = engine.dialect.name
        return EngineReadinessReport(
            db_type=dialect,
            findings=(),
            checked_at=datetime.now(UTC),
            dynamic=False,
            supported=dialect in self.SUPPORTED_DB_TYPES,
            error="La verificación del motor no está disponible (no terminó o falló)",
        )

    @staticmethod
    def describe_engine(engine: Engine) -> str:
        """``dialecto · host:puerto/base`` de ``engine``, sin usuario ni contraseña (títulos de informes).

        Example:
            >>> EngineReadinessAdvisor.describe_engine(create_engine("postgresql://u:p@db:5432/app"))
            'postgresql · db:5432/app'
        """
        url = engine.url
        location = f"{url.host}:{url.port}" if url.host and url.port else str(url.host or "")
        target = f"{location}/{url.database}" if location and url.database else str(location or url.database or "")
        return f"{engine.dialect.name} · {target}" if target else engine.dialect.name

    def _verify_and_store(self, engine: Engine) -> None:
        """Verifica ``engine`` con :meth:`report` (con conexión o, si no la hay, solo estáticos) y guarda el informe."""
        checked_at = datetime.now(UTC)
        dialect = engine.dialect.name
        findings: list[AdvisoryFinding] | None = None
        dynamic = False
        error: str | None = None
        try:
            conn_params = self._conn_params_from_engine(engine)
            try:
                with engine.connect() as conn:
                    findings = self.report(dialect, conn_params, connection=conn)
                    dynamic = True
            except Exception as exc:
                # Sin conexión activa, solo checks estáticos; si ya se informó (falló el cierre), no se repite
                if findings is None:
                    error = f"Sin conexión para los checks dinámicos ({type(exc).__name__})"
                    try:
                        findings = self.report(dialect, conn_params)
                    except Exception as static_exc:
                        error = f"No se pudo verificar el motor ({type(static_exc).__name__})"
                        logger.debug(f"Error en verificación de motor '{dialect}': {static_exc}")
            report = EngineReadinessReport(
                db_type=dialect,
                findings=tuple(findings or ()),
                checked_at=checked_at,
                dynamic=dynamic,
                supported=dialect in self.SUPPORTED_DB_TYPES,
                error=error,
            )
            with self._reported_lock:
                self._reports[engine] = report
        except Exception as exc:  # el informe es opcional: nunca debe interrumpir a quien crea el BulkCrud
            logger.debug(f"No se pudo guardar la verificación del motor '{dialect}': {type(exc).__name__}")

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
            ac_findings = self._check_mysql_autocommit(conn_params["autocommit"])
            if ac_findings is None:
                findings.append(
                    AdvisoryFinding(
                        level="CRITICAL",
                        param="autocommit",
                        current=str(conn_params["autocommit"]),
                        recommendation="autocommit debe ser true/false (booleano o string: 'true', 'false', 'yes', 'no', '1', '0')",
                    )
                )
                return findings
            findings.extend(ac_findings)

        for param, minimum, unit, recommendation in self._MYSQL_MINIMUMS:
            if param in conn_params:
                try:
                    value = _to_int(conn_params[param], param, "mysql")
                    findings.append(self._minimum_finding(param, value, minimum, unit, recommendation))
                except ValueError:
                    findings.append(
                        AdvisoryFinding(
                            level="CRITICAL",
                            param=param,
                            current=str(conn_params[param]),
                            recommendation=f"{param} debe ser entero",
                        )
                    )

        pt_findings = self._check_mysql_pool_timeout(conn_params.get("pool_timeout", 30))
        if pt_findings is None:
            findings.append(
                AdvisoryFinding(
                    level="CRITICAL",
                    param="pool_timeout",
                    current=str(conn_params.get("pool_timeout")),
                    recommendation="pool_timeout debe ser entero",
                )
            )
            return findings
        findings.extend(pt_findings)

        # Checks dinámicos: delegar en MySQLVariableValidator existente
        if connection is not None:
            findings.extend(self._check_mysql_dynamic(connection))

        return findings

    @staticmethod
    def _check_mysql_autocommit(value: Any) -> list[AdvisoryFinding] | None:
        """Valida y reporta autocommit. Retorna None si hay error crítico (para interrumpir checks)."""
        try:
            autocommit: bool = _to_bool(value, "autocommit", "mysql")
        except ValueError:
            return None
        findings: list[AdvisoryFinding] = [
            AdvisoryFinding(
                level="WARNING" if autocommit else "OK",
                param="autocommit",
                current=str(autocommit),
                recommendation="autocommit=True confirma cada INSERT individualmente; usar transacciones para bulk"
                if autocommit
                else "",
            )
        ]
        return findings

    @staticmethod
    def _check_mysql_pool_timeout(value: Any) -> list[AdvisoryFinding] | None:
        """Valida y reporta pool_timeout. Retorna None si hay error crítico (para interrumpir checks)."""
        try:
            pool_timeout: int = _to_int(value, "pool_timeout", "mysql")
        except ValueError:
            return None  # Señal de error crítico al llamador
        findings: list[AdvisoryFinding] = []
        if pool_timeout < 10:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_timeout",
                    current=f"{pool_timeout}s",
                    recommendation="Recomendado ≥10 s para evitar timeouts en picos de carga",
                )
            )
        return findings

    @staticmethod
    def _minimum_finding(param: str, value: int, minimum: int, unit: str, recommendation: str) -> AdvisoryFinding:
        """WARNING con ``recommendation`` si ``value`` queda por debajo de ``minimum``; OK en otro caso."""
        if value < minimum:
            return AdvisoryFinding(
                level="WARNING", param=param, current=f"{value}{unit}", recommendation=recommendation
            )
        return AdvisoryFinding(level="OK", param=param, current=f"{value}{unit}", recommendation="")

    @staticmethod
    def _check_mysql_thresholds(
        validator: Any, current: dict[str, Any], thresholds: dict[str, int]
    ) -> list[AdvisoryFinding]:
        """Evalúa variables con umbral mínimo y devuelve hallazgos ordenados."""
        findings: list[AdvisoryFinding] = []
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
        return findings

    @staticmethod
    def _check_mysql_flush_log_at_trx_commit(value: Any) -> AdvisoryFinding | None:
        """Evalúa innodb_flush_log_at_trx_commit: durabilidad primero (decisión A-05, 2026-10-16).

        Es una variable global: el advisor no recomienda rebajar la durabilidad de todo el servidor. 1 (por defecto, el
        único valor ACID) es OK; 2 se informa (pierde hasta ~1 s de commits si cae el SO) y 0 se avisa (también si cae
        mysqld). Hasta v2.1.0, 1 era WARNING («cambiar a 2»), 2 OK y 0 CRITICAL.
        """
        if value is None:
            return None
        if value == 1:
            return AdvisoryFinding(level="OK", param="innodb_flush_log_at_trx_commit", current="1", recommendation="")
        if value == 2:
            return AdvisoryFinding(
                level="INFO",
                param="innodb_flush_log_at_trx_commit",
                current="2",
                recommendation="Durabilidad reducida: si cae el sistema operativo se pierde hasta ~1 s de commits "
                "confirmados; aceptable solo durante una ventana de carga; al terminar: "
                "SET GLOBAL innodb_flush_log_at_trx_commit = 1;",
            )
        return AdvisoryFinding(
            level="WARNING",
            param="innodb_flush_log_at_trx_commit",
            current=str(value),
            recommendation="Se pierde hasta ~1 s de commits confirmados también si solo cae mysqld; volver a 1 "
            "(SET GLOBAL innodb_flush_log_at_trx_commit = 1;) o, solo durante una carga, 2",
        )

    @staticmethod
    def _check_mysql_log_file_size(validator: Any, value: Any) -> AdvisoryFinding | None:
        """Evalúa innodb_log_file_size."""
        if value is None:
            return None
        log_file_fmt = validator.format_bytes(value)
        warn_threshold = 512 * 1_048_576
        if value < warn_threshold:
            return AdvisoryFinding(
                level="INFO",
                param="innodb_log_file_size",
                current=log_file_fmt,
                recommendation=f"Para bulk en datasets >10GB: aumentar a 1–2 GB "
                f"(actual: {log_file_fmt}); evita rotación frecuente de redo log; "
                f"MySQL 8.0.30+: ajustar innodb_redo_log_capacity (dinámica; innodb_log_file_size está obsoleta); "
                f"MySQL 5.7 y MariaDB < 10.9: en my.cnf, requiere reinicio",
            )
        return AdvisoryFinding(level="OK", param="innodb_log_file_size", current=log_file_fmt, recommendation="")

    @staticmethod
    def _check_mysql_write_io_threads(value: Any) -> AdvisoryFinding | None:
        """Evalúa innodb_write_io_threads."""
        if value is None:
            return None
        if value < 4:
            return AdvisoryFinding(
                level="INFO",
                param="innodb_write_io_threads",
                current=str(value),
                recommendation="En servidores SSD con ≥4 CPUs: aumentar a nCPU/2 "
                "para paralelismo de escritura; en my.cnf (innodb_write_io_threads = <n>): en MySQL no es dinámica "
                "y requiere reinicio",
            )
        return AdvisoryFinding(level="OK", param="innodb_write_io_threads", current=str(value), recommendation="")

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
            findings.extend(self._check_mysql_thresholds(validator, current, thresholds))

            checks = (
                self._check_mysql_flush_log_at_trx_commit(current.get("innodb_flush_log_at_trx_commit")),
                self._check_mysql_log_file_size(validator, current.get("innodb_log_file_size")),
                self._check_mysql_write_io_threads(current.get("innodb_write_io_threads")),
            )
            findings.extend(check for check in checks if check is not None)
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


__all__: list[str] = ["AdvisoryFinding", "EngineReadinessAdvisor", "EngineReadinessReport"]
