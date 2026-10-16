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

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from ._advisory import AdvisoryFinding, EngineReadinessReport, ReadinessValidator

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine

logger: logging.Logger = logging.getLogger(__name__)

_LEVEL_ORDER: dict[str, int] = {"OK": 0, "INFO": 1, "WARNING": 2, "CRITICAL": 3}

#: Nombre de la librería para los dialectos de SQLAlchemy que se llaman distinto (T-10, decisión 2026-10-16): los
#: informes usan el ``db_type`` de los managers (``sqlserver``), venga el informe de un manager o de un engine.
_REPORT_NAMES: dict[str, str] = {"mssql": "sqlserver"}
_LEVEL_ICONS: dict[str, str] = {"OK": "✅  OK  ", "INFO": "ℹ️  INFO", "WARNING": "⚠️  WARN", "CRITICAL": "🔴  CRIT"}


def _mysql() -> ReadinessValidator:
    from .mariadb._readiness import MySQLReadinessValidator

    return MySQLReadinessValidator()


def _postgresql() -> ReadinessValidator:
    from .postgresql._variables import PostgreSQLVariableValidator

    return PostgreSQLVariableValidator()


def _sqlserver() -> ReadinessValidator:
    from .sqlserver._variables import SQLServerVariableValidator

    return SQLServerVariableValidator()


def _oracle() -> ReadinessValidator:
    from .oracle._variables import OracleVariableValidator

    return OracleVariableValidator()


def _sqlite() -> ReadinessValidator:
    from .sqlite._variables import SQLiteVariableValidator

    return SQLiteVariableValidator()


#: Registro motor → fábrica del validador (Strategy, T-06): añadir un motor no toca :class:`EngineReadinessAdvisor`.
_VALIDATORS: dict[str, Callable[[], ReadinessValidator]] = {
    "mysql": _mysql,
    "mariadb": _mysql,
    "postgresql": _postgresql,
    "mssql": _sqlserver,
    "sqlserver": _sqlserver,
    "oracle": _oracle,
    "sqlite": _sqlite,
}


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

    #: Motores con checks específicos en :meth:`check` (las claves del registro); el resto devuelve una lista vacía.
    SUPPORTED_DB_TYPES: ClassVar[frozenset[str]] = frozenset(_VALIDATORS)

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

        factory = _VALIDATORS.get(engine)
        if factory is None:
            logger.debug(f"EngineReadinessAdvisor: motor '{db_type}' sin checks específicos")
        else:
            findings.extend(self._run_validator(engine, factory, conn_params, connection))

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

        Examples:
            >>> report = EngineReadinessAdvisor().assess("mysql", {"pool_size": 2})
            >>> [(f.level, f.param) for f in report.findings]
            [('WARNING', 'pool_size')]
        """
        checked_at = datetime.now(UTC)
        db_type = self.report_name(db_type)
        if db_type not in self.SUPPORTED_DB_TYPES:
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

    async def assess_async(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        engine: AsyncEngine | None = None,
    ) -> EngineReadinessReport:
        """:meth:`assess` con un ``AsyncEngine``: los checks dinámicos usan su conexión vía ``run_sync``.

        Mismo contrato que :meth:`assess` (T-10, 2026-10-16): sin engine o sin conexión, solo los estáticos y el motivo en
        ``error``; nunca un segundo engine síncrono.

        Args:
            db_type: Motor (``postgresql``, ``mysql``, ``mariadb``, ``oracle``, ``mssql``/``sqlserver``, ``sqlite``).
            conn_params: Parámetros de conexión/pool.
            engine: ``AsyncEngine`` de SQLAlchemy para los checks dinámicos (opcional).

        Returns:
            El informe; ``supported=False`` si el motor no tiene checks.
        """
        if engine is None or self.report_name(db_type) not in self.SUPPORTED_DB_TYPES:
            return self.assess(db_type, conn_params)
        checked_at = datetime.now(UTC)
        name = self.report_name(db_type)
        dynamic_findings: list[AdvisoryFinding] | None = None
        error: str | None = None
        try:
            async with engine.connect() as conn:
                dynamic_findings = await conn.run_sync(
                    lambda sync_conn: self.check(name, conn_params, connection=sync_conn)
                )
        except Exception as exc:
            # Como en assess(): si ya hay hallazgos, falló el cierre y se conservan; del error, solo el tipo.
            if dynamic_findings is None:
                error = f"Sin conexión para los checks dinámicos ({type(exc).__name__})"
            logger.debug(f"EngineReadinessAdvisor.assess_async: '{name}' sin conexión: {type(exc).__name__}")
        if dynamic_findings is not None:
            return EngineReadinessReport(
                db_type=name, findings=tuple(dynamic_findings), checked_at=checked_at, dynamic=True, supported=True
            )
        return EngineReadinessReport(
            db_type=name,
            findings=tuple(self.check(name, conn_params)),
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

        Examples:
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
        dialect = self.report_name(engine.dialect.name)
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

        Examples:
            >>> EngineReadinessAdvisor.describe_engine(create_engine("postgresql://u:p@db:5432/app"))
            'postgresql · db:5432/app'
        """
        url = engine.url
        location = f"{url.host}:{url.port}" if url.host and url.port else str(url.host or "")
        target = f"{location}/{url.database}" if location and url.database else str(location or url.database or "")
        name = EngineReadinessAdvisor.report_name(engine.dialect.name)
        return f"{name} · {target}" if target else name

    @staticmethod
    def report_name(db_type: str) -> str:
        """Nombre del motor en los informes: en minúsculas y con el de la librería (``mssql`` → ``sqlserver``).

        Examples:
            >>> EngineReadinessAdvisor.report_name("mssql"), EngineReadinessAdvisor.report_name(" PostgreSQL ")
            ('sqlserver', 'postgresql')
        """
        name = db_type.lower().strip()
        return _REPORT_NAMES.get(name, name)

    def _verify_and_store(self, engine: Engine) -> None:
        """Verifica ``engine`` con :meth:`report` (con conexión o, si no la hay, solo estáticos) y guarda el informe."""
        checked_at = datetime.now(UTC)
        dialect = self.report_name(engine.dialect.name)
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
                        # T-08: report() no lanza por fallos de los checks; esto es un error interno (WARNING con traza).
                        error = f"No se pudo verificar el motor ({type(static_exc).__name__})"
                        logger.warning(
                            f"EngineReadinessAdvisor: error interno al verificar '{dialect}' sin conexión "
                            f"({type(static_exc).__name__})",
                            exc_info=True,
                        )
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
            # T-08: un fallo aquí es un error interno (WARNING con traza; antes, DEBUG).
            logger.warning(
                f"EngineReadinessAdvisor: error interno al guardar la verificación de '{dialect}' "
                f"({type(exc).__name__})",
                exc_info=True,
            )

    @staticmethod
    def _run_validator(
        engine: str, factory: Callable[[], ReadinessValidator], conn_params: dict[str, Any], connection: Any
    ) -> list[AdvisoryFinding]:
        """Estáticos y, con ``connection``, dinámicos del validador de ``engine``; nunca lanza.

        T-08 (2026-10-16): los validadores capturan lo esperable (``SQLAlchemyError``, valores que no se pueden
        interpretar); lo que llega aquí es un error interno y se registra en WARNING con traza (antes, DEBUG). Un error
        en los dinámicos conserva los estáticos (antes, en PostgreSQL, SQL Server, Oracle y SQLite se perdían todos).
        """
        try:
            validator = factory()
            findings = validator.check_static(conn_params)
        except Exception as exc:
            EngineReadinessAdvisor._log_internal_error(engine, "estáticos", exc)
            return []
        if connection is None:
            return findings
        try:
            findings.extend(validator.check_dynamic(connection, conn_params))
        except Exception as exc:
            EngineReadinessAdvisor._log_internal_error(engine, "dinámicos", exc)
        return findings

    @staticmethod
    def _log_internal_error(engine: str, kind: str, exc: Exception) -> None:
        """WARNING con traza de un error interno de los checks (``kind``: ``estáticos`` o ``dinámicos``)."""
        logger.warning(
            f"EngineReadinessAdvisor: error interno en los checks {kind} de '{engine}' ({type(exc).__name__}); "
            f"se omiten",
            exc_info=exc,
        )

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


__all__: list[str] = ["AdvisoryFinding", "EngineReadinessAdvisor", "EngineReadinessReport"]
