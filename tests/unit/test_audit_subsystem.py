"""Unit tests for the _audit/ subsystem: repository, service, exporters, AuditManager."""

from __future__ import annotations

import logging

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from util_bbdd.bulk._audit.errors import (
    AuditConfigError,
    AuditFileError,
    AuditValidationError,
)
from util_bbdd.bulk._audit.repository import AuditCsvRepository
from util_bbdd.bulk._audit.service import AuditAnalyticsService
from util_bbdd.bulk.audit import AuditManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_COLUMNS = ["timestamp", "tabla", "motor", "operacion", "total_filas", "tiempo_seg", "sql"]


@pytest.fixture()
def repo(tmp_path: Path) -> AuditCsvRepository:
    csv_path = tmp_path / "audit.csv"
    return AuditCsvRepository(
        audit_csv_path=csv_path,
        columnas_auditoria=_COLUMNS,
        logger=logging.getLogger("test"),
        cache_enabled=True,
        cache_ttl_seconds=60,
    )


@pytest.fixture()
def repo_no_path() -> AuditCsvRepository:
    return AuditCsvRepository(
        audit_csv_path=None,
        columnas_auditoria=_COLUMNS,
        logger=logging.getLogger("test"),
    )


@pytest.fixture()
def populated_repo(repo: AuditCsvRepository) -> AuditCsvRepository:
    repo.registrar_operacion(tabla="orders", motor="sqlite", operacion="INSERT", rowcount=10, elapsed=0.5)
    repo.registrar_operacion(tabla="orders", motor="sqlite", operacion="UPDATE", rowcount=5, elapsed=0.1)
    repo.registrar_operacion(tabla="users", motor="sqlite", operacion="DELETE", rowcount=2, elapsed=8.0)
    return repo


@pytest.fixture()
def service(populated_repo: AuditCsvRepository) -> AuditAnalyticsService:
    return AuditAnalyticsService(repository=populated_repo, logger=logging.getLogger("test"))


@pytest.fixture()
def manager(tmp_path: Path) -> AuditManager:
    return AuditManager(audit_csv_path=tmp_path / "audit.csv")


@pytest.fixture()
def populated_manager(manager: AuditManager) -> AuditManager:
    manager._repository.registrar_operacion(
        tabla="orders", motor="sqlite", operacion="INSERT", rowcount=10, elapsed=0.5
    )
    manager._repository.registrar_operacion(tabla="users", motor="sqlite", operacion="UPDATE", rowcount=3, elapsed=0.2)
    return manager


# ---------------------------------------------------------------------------
# AuditCsvRepository — escritura y lectura
# ---------------------------------------------------------------------------


class TestRepositoryWrite:
    def test_registrar_operacion_crea_csv(self, repo: AuditCsvRepository, tmp_path: Path) -> None:
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
        assert (tmp_path / "audit.csv").exists()

    def test_registrar_operacion_escribe_fila(self, repo: AuditCsvRepository) -> None:
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=5, elapsed=1.234)
        df = repo.leer_auditoria(usar_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["tabla"] == "t"
        assert df.iloc[0]["total_filas"] == 5

    def test_tiempo_almacenado_con_punto_decimal(self, repo: AuditCsvRepository) -> None:
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=1.5)
        df = repo.leer_auditoria(usar_cache=False)
        assert df.iloc[0]["tiempo_seg"] == pytest.approx(1.5)

    def test_registrar_sin_path_lanza_error(self, repo_no_path: AuditCsvRepository) -> None:
        with pytest.raises(AuditConfigError):
            repo_no_path.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)

    def test_multiples_filas_acumulan(self, populated_repo: AuditCsvRepository) -> None:
        df = populated_repo.leer_auditoria(usar_cache=False)
        assert len(df) == 3


class TestRepositoryCache:
    def test_cache_warm_after_read(self, populated_repo: AuditCsvRepository) -> None:
        populated_repo.leer_auditoria()
        assert populated_repo.es_cache_valido()

    def test_limpiar_cache_invalida(self, populated_repo: AuditCsvRepository) -> None:
        populated_repo.leer_auditoria()
        populated_repo.limpiar_cache()
        assert not populated_repo.es_cache_valido()

    def test_registrar_invalida_cache(self, populated_repo: AuditCsvRepository) -> None:
        populated_repo.leer_auditoria()
        populated_repo.registrar_operacion(tabla="new", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.0)
        assert not populated_repo.es_cache_valido()

    def test_usar_cache_false_relectura_directa(self, populated_repo: AuditCsvRepository) -> None:
        populated_repo.leer_auditoria()
        df = populated_repo.leer_auditoria(usar_cache=False)
        assert len(df) == 3

    def test_leer_sin_path_lanza_error(self, repo_no_path: AuditCsvRepository) -> None:
        with pytest.raises(AuditConfigError):
            repo_no_path.leer_auditoria()

    def test_leer_csv_inexistente_lanza_file_error(self, tmp_path: Path) -> None:
        repo = AuditCsvRepository(
            audit_csv_path=tmp_path / "nonexistent.csv",
            columnas_auditoria=_COLUMNS,
            logger=logging.getLogger("test"),
        )
        with pytest.raises(AuditFileError):
            repo.leer_auditoria()


# ---------------------------------------------------------------------------
# AuditAnalyticsService
# ---------------------------------------------------------------------------


class TestServiceEstadisticas:
    def test_total_operaciones(self, service: AuditAnalyticsService) -> None:
        stats = service.obtener_estadisticas()
        assert stats["total_operaciones"] == 3

    def test_total_filas_procesadas(self, service: AuditAnalyticsService) -> None:
        stats = service.obtener_estadisticas()
        assert stats["total_filas_procesadas"] == 17

    def test_operaciones_por_tipo(self, service: AuditAnalyticsService) -> None:
        counts = service.obtener_operaciones_por_tipo()
        assert counts["INSERT"] == 1
        assert counts["UPDATE"] == 1
        assert counts["DELETE"] == 1

    def test_operaciones_por_tabla(self, service: AuditAnalyticsService) -> None:
        counts = service.obtener_operaciones_por_tabla()
        assert counts["orders"] == 2
        assert counts["users"] == 1


class TestServiceFiltros:
    def test_filtrar_por_operacion(self, service: AuditAnalyticsService) -> None:
        df = service.filtrar_por_operacion("INSERT")
        assert len(df) == 1
        assert df.iloc[0]["tabla"] == "orders"

    def test_filtrar_operacion_invalida_lanza_error(self, service: AuditAnalyticsService) -> None:
        with pytest.raises(AuditValidationError):
            service.filtrar_por_operacion("UPSERT")

    def test_filtrar_por_tabla(self, service: AuditAnalyticsService) -> None:
        df = service.filtrar_por_tabla("users")
        assert len(df) == 1

    def test_filtrar_tabla_vacia_lanza_error(self, service: AuditAnalyticsService) -> None:
        with pytest.raises(AuditValidationError):
            service.filtrar_por_tabla("")

    def test_filtrar_por_motor(self, service: AuditAnalyticsService) -> None:
        df = service.filtrar_por_motor("sqlite")
        assert len(df) == 3

    def test_obtener_operaciones_lentas(self, service: AuditAnalyticsService) -> None:
        df = service.obtener_operaciones_lentas(umbral_segundos=5.0)
        assert len(df) == 1
        assert df.iloc[0]["tabla"] == "users"

    def test_filtrar_multiple_none_no_filtra(self, service: AuditAnalyticsService) -> None:
        df = service.filtrar_multiple()
        assert len(df) == 3

    def test_filtrar_multiple_operacion_none_no_aplica_filtro(self, service: AuditAnalyticsService) -> None:
        df = service.filtrar_multiple(operacion=None)
        assert len(df) == 3

    def test_filtrar_multiple_combina_criterios(self, service: AuditAnalyticsService) -> None:
        df = service.filtrar_multiple(tabla="orders", operacion="INSERT")
        assert len(df) == 1

    def test_filtrar_por_rango_tiempo(self, service: AuditAnalyticsService) -> None:
        inicio = datetime.now() - timedelta(minutes=1)
        fin = datetime.now() + timedelta(minutes=1)
        df = service.filtrar_por_rango_tiempo(inicio, fin)
        assert len(df) == 3

    def test_filtrar_rango_invalido_lanza_error(self, service: AuditAnalyticsService) -> None:
        with pytest.raises(AuditValidationError):
            service.filtrar_por_rango_tiempo(
                datetime.now() + timedelta(hours=1),
                datetime.now(),
            )


# ---------------------------------------------------------------------------
# AuditManager — fachada
# ---------------------------------------------------------------------------


class TestAuditManagerFacade:
    def test_registrar_operacion_persiste(self, populated_manager: AuditManager) -> None:
        df = populated_manager.leer_auditoria()
        assert len(df) == 2

    def test_registrar_sin_path_no_lanza(self) -> None:
        manager = AuditManager(audit_csv_path=None)
        manager.registrar_operacion("t", "sqlite", "INSERT", 1, 0.1)

    def test_obtener_estadisticas(self, populated_manager: AuditManager) -> None:
        stats = populated_manager.obtener_estadisticas()
        assert stats["total_operaciones"] == 2

    def test_limpiar_cache(self, populated_manager: AuditManager) -> None:
        populated_manager.leer_auditoria()
        populated_manager.limpiar_cache()
        assert not populated_manager._repository.es_cache_valido()

    def test_invalidar_cache_alias(self, populated_manager: AuditManager) -> None:
        populated_manager.leer_auditoria()
        populated_manager.invalidar_cache()
        assert not populated_manager._repository.es_cache_valido()

    def test_obtener_historial_sin_csv_path_no_lanza(self) -> None:
        manager = AuditManager(audit_csv_path=None)
        assert manager.obtener_historial_transacciones() == []

    def test_filtrar_por_operacion(self, populated_manager: AuditManager) -> None:
        df = populated_manager.filtrar_por_operacion("INSERT")
        assert len(df) == 1

    def test_obtener_operaciones_lentas(self, populated_manager: AuditManager) -> None:
        df = populated_manager.obtener_operaciones_lentas(umbral_segundos=0.3)
        assert len(df) == 1


# ---------------------------------------------------------------------------
# AuditTransaction — context manager
# ---------------------------------------------------------------------------


class TestAuditTransaction:
    def test_transaccion_exitosa_registra_historial(self, manager: AuditManager) -> None:
        with manager.iniciar_transaccion("carga-inicial") as tx:
            tx.agregar_operacion("orders", "sqlite", "INSERT", 10, 0.5)
        historial = manager.obtener_historial_transacciones()
        assert len(historial) == 1
        assert historial[0]["nombre"] == "carga-inicial"
        assert historial[0]["exito"] is True

    def test_transaccion_fallida_marca_exito_false(self, manager: AuditManager) -> None:
        with pytest.raises(ValueError):
            with manager.iniciar_transaccion("tx-fallida") as tx:
                tx.agregar_operacion("t", "sqlite", "INSERT", 1, 0.1)
                raise ValueError("error simulado")
        historial = manager.obtener_historial_transacciones()
        assert historial[0]["exito"] is False

    def test_agregar_operacion_fuera_de_contexto_lanza_error(self, manager: AuditManager) -> None:
        tx = manager.iniciar_transaccion("tx")
        with tx:
            pass
        with pytest.raises(AuditValidationError):
            tx.agregar_operacion("t", "sqlite", "INSERT", 1, 0.1)

    def test_duracion_segundos_calculada(self, manager: AuditManager) -> None:
        with manager.iniciar_transaccion("tx") as tx:
            pass
        assert tx.duracion_segundos >= 0.0

    def test_total_filas_suma_operaciones(self, manager: AuditManager) -> None:
        with manager.iniciar_transaccion("tx") as tx:
            tx.agregar_operacion("t", "sqlite", "INSERT", 5, 0.1)
            tx.agregar_operacion("t", "sqlite", "INSERT", 3, 0.1)
        assert tx.total_filas == 8

    def test_audit_error_none_en_exito(self, manager: AuditManager) -> None:
        with manager.iniciar_transaccion("tx") as tx:
            pass
        assert tx.audit_error is None

    def test_nombre_vacio_lanza_error(self, manager: AuditManager) -> None:
        with pytest.raises(AuditValidationError):
            manager.iniciar_transaccion("   ")

    def test_obtener_resumen_estructura(self, manager: AuditManager) -> None:
        with manager.iniciar_transaccion("resumen-test") as tx:
            tx.agregar_operacion("t", "sqlite", "INSERT", 1, 0.0)
        resumen = tx.obtener_resumen()
        assert set(resumen.keys()) >= {
            "nombre",
            "exito",
            "duracion_segundos",
            "total_operaciones",
            "total_filas",
            "operaciones",
        }
        assert resumen["nombre"] == "resumen-test"
        assert resumen["exito"] is True
