"""Checks de condiciones de ejecución de MySQL/MariaDB para ``EngineReadinessAdvisor`` (interno).

T-06 (refactor 2026-10-16, sin cambios funcionales): esta lógica vivía dentro de ``EngineReadinessAdvisor``
(``_check_mysql*``); ahora es un validador con la misma interfaz que los del resto de motores (``check_static`` /
``check_dynamic``, Protocol ``ReadinessValidator``). Los dinámicos leen las variables con ``MySQLVariableValidator``.
No se exporta: el punto de entrada es ``EngineReadinessAdvisor``.
"""

from __future__ import annotations

import logging

from typing import Any, ClassVar

from .._advisory import AdvisoryFinding
from ..config import _to_bool, _to_int
from ._config import MySQLOptimalConfig
from ._variables import MySQLVariableValidator

logger: logging.Logger = logging.getLogger(__name__)


class MySQLReadinessValidator:
    """Checks estáticos (``conn_params``) y dinámicos (``SHOW VARIABLES``) de MySQL y MariaDB.

    Una instancia por verificación: :meth:`check_static` recuerda si debe omitirse :meth:`check_dynamic` (un
    ``autocommit`` o ``pool_timeout`` inválido corta los checks, como antes del refactor).
    """

    #: Checks estáticos con mínimo: (parámetro, mínimo, unidad, recomendación si queda por debajo).
    MINIMUMS: ClassVar[tuple[tuple[str, int, str, str], ...]] = (
        ("pool_size", 5, "", "Mínimo 5 para cargas concurrentes"),
        # T-03: el texto decía «≥60 s» con mínimo 30 (45 s salía OK); se ajusta el texto, no el umbral del WARNING.
        ("write_timeout", 30, "s", "Mínimo 30 s; en cargas masivas largas, 60 s o más evita 'Lost connection'"),
        ("read_timeout", 30, "s", "Recomendado ≥30 s"),
    )

    def __init__(self) -> None:
        self._dynamic_allowed: bool = True

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Checks de pool/config: solo los parámetros presentes.

        ``report_once()`` no conoce autocommit ni los timeouts del driver (no están en ``engine.url``) y un valor por
        defecto no debe presentarse como leído.
        """
        findings: list[AdvisoryFinding] = []
        self._dynamic_allowed = True

        if "autocommit" in conn_params:
            ac_findings = self._check_autocommit(conn_params["autocommit"])
            if ac_findings is None:
                findings.append(
                    AdvisoryFinding(
                        level="CRITICAL",
                        param="autocommit",
                        current=str(conn_params["autocommit"]),
                        recommendation="autocommit debe ser true/false (booleano o string: 'true', 'false', 'yes', 'no', '1', '0')",
                    )
                )
                self._dynamic_allowed = False
                return findings
            findings.extend(ac_findings)

        for param, minimum, unit, recommendation in self.MINIMUMS:
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

        pt_findings = self._check_pool_timeout(conn_params.get("pool_timeout", 30))
        if pt_findings is None:
            findings.append(
                AdvisoryFinding(
                    level="CRITICAL",
                    param="pool_timeout",
                    current=str(conn_params.get("pool_timeout")),
                    recommendation="pool_timeout debe ser entero",
                )
            )
            self._dynamic_allowed = False
            return findings
        findings.extend(pt_findings)
        return findings

    def check_dynamic(self, connection: Any, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Variables del servidor con ``MySQLVariableValidator``; un fallo deja los hallazgos ya obtenidos."""
        findings: list[AdvisoryFinding] = []
        if not self._dynamic_allowed:
            return findings
        try:
            validator = MySQLVariableValidator(connection)
            current = validator.read_variables()
            if not current:
                return findings

            recommended = MySQLOptimalConfig.production()
            thresholds = {
                "innodb_buffer_pool_size": recommended.innodb_buffer_pool_size,
                "max_allowed_packet": recommended.max_allowed_packet,
            }
            findings.extend(self._check_thresholds(validator, current, thresholds))

            checks = (
                self._check_flush_log_at_trx_commit(current.get("innodb_flush_log_at_trx_commit")),
                self._check_log_file_size(validator, current.get("innodb_log_file_size")),
                self._check_write_io_threads(current.get("innodb_write_io_threads")),
            )
            findings.extend(check for check in checks if check is not None)
        except Exception as exc:
            logger.debug(f"MySQLReadinessValidator.check_dynamic: {type(exc).__name__}: {exc}")
        return findings

    @staticmethod
    def _check_autocommit(value: Any) -> list[AdvisoryFinding] | None:
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
    def _check_pool_timeout(value: Any) -> list[AdvisoryFinding] | None:
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
    def _check_thresholds(
        validator: MySQLVariableValidator, current: dict[str, int], thresholds: dict[str, int]
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
    def _check_flush_log_at_trx_commit(value: int | None) -> AdvisoryFinding | None:
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
    def _check_log_file_size(validator: MySQLVariableValidator, value: int | None) -> AdvisoryFinding | None:
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
    def _check_write_io_threads(value: int | None) -> AdvisoryFinding | None:
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


__all__: list[str] = ["MySQLReadinessValidator"]
