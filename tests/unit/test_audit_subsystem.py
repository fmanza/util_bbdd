"""Unit tests for the _audit/ subsystem: repository, service, exporters, AuditManager."""

from __future__ import annotations

import logging
import shutil

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from util_bbdd.bulk._audit.errors import (
    AuditConfigError,
    AuditFileError,
    AuditValidationError,
)
from util_bbdd.bulk._audit.repository import AuditCsvRepository, _get_file_lock
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

    def test_fichero_vacio_existente_recibe_cabecera(self, repo: AuditCsvRepository, tmp_path: Path) -> None:
        # H4 (audit-code 2026-09-25): un CSV de 0 bytes existe, y antes la primera fila de datos quedaba de cabecera.
        (tmp_path / "audit.csv").touch()
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=5, elapsed=0.1)
        df = repo.leer_auditoria(usar_cache=False)
        assert list(df.columns) == _COLUMNS
        assert len(df) == 1
        assert df.iloc[0]["total_filas"] == 5

    def test_cabecera_no_valida_se_aparta_y_se_empieza_otro(
        self, repo: AuditCsvRepository, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # CSV re-guardado con otra herramienta (cada línea entrecomillada): antes se le añadían filas y ningún lector
        # podía leerlo (el volcado se quedaba sin informe Excel).
        csv_path = tmp_path / "audit.csv"
        roto = '"' + "\t".join(_COLUMNS) + '"\r\n"2026-06-02 10:10:59\tt\tMARIADB\tINSERT\t4\t0,346\tNo"\r\n'
        csv_path.write_text(roto, encoding="utf-8", newline="")

        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=7, elapsed=0.1)
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=8, elapsed=0.1)

        df = repo.leer_auditoria(usar_cache=False)
        assert list(df.columns) == _COLUMNS
        assert df["total_filas"].tolist() == [7, 8]
        apartados = list(tmp_path.glob("audit.invalid-*.csv"))
        assert len(apartados) == 1
        assert apartados[0].read_text(encoding="utf-8") == roto.replace("\r\n", "\n")  # contenido intacto
        assert "cabecera no válida" in caplog.text

    def test_apartado_con_el_mismo_nombre_no_se_pisa(self, tmp_path: Path) -> None:
        # L1: dos apartados en el mismo segundo; en Windows el renombrado a un nombre existente fallaría.
        csv_path = tmp_path / "audit.csv"
        primero = AuditCsvRepository._ruta_apartado(csv_path)
        primero.write_text("previo", encoding="utf-8")

        segundo = AuditCsvRepository._ruta_apartado(csv_path)

        assert segundo != primero
        assert segundo.name.startswith(primero.stem) and segundo.stem.endswith("_2")

    def test_si_no_se_puede_apartar_lanza_audit_file_error_sin_tocar_el_fichero(
        self, repo: AuditCsvRepository, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "audit.csv"
        csv_path.write_text('"cabecera rota"\n', encoding="utf-8")

        with (
            patch.object(Path, "rename", side_effect=PermissionError("bloqueado")),
            pytest.raises(AuditFileError, match="no se pudo apartar"),
        ):
            repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)

        assert csv_path.read_text(encoding="utf-8") == '"cabecera rota"\n'

    def test_varios_hilos_con_cabecera_rota_apartan_una_sola_vez(self, tmp_path: Path) -> None:
        import threading

        csv_path = tmp_path / "audit.csv"
        csv_path.write_text('"' + "\t".join(_COLUMNS) + '"\n', encoding="utf-8")
        repos = [
            AuditCsvRepository(audit_csv_path=csv_path, columnas_auditoria=_COLUMNS, logger=logging.getLogger("test"))
            for _ in range(8)
        ]
        hilos = [
            threading.Thread(
                target=r.registrar_operacion,
                kwargs={"tabla": "t", "motor": "sqlite", "operacion": "INSERT", "rowcount": 1, "elapsed": 0.1},
            )
            for r in repos
        ]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert len(list(tmp_path.glob("audit.invalid-*"))) == 1
        assert len(repos[0].leer_auditoria(usar_cache=False)) == 8

    def test_cambiar_las_columnas_vuelve_a_comprobar_la_cabecera(
        self, repo: AuditCsvRepository, tmp_path: Path
    ) -> None:
        # L2: la comprobación se hace una vez por (ruta, columnas), no solo por ruta.
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
        with patch.object(repo, "_asegurar_cabecera", wraps=repo._asegurar_cabecera) as spy:
            repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
            assert spy.call_count == 0
            repo.columnas_auditoria = [*_COLUMNS[:-1], "otra"]
            repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
            assert spy.call_count == 1

    def test_cabecera_valida_no_se_aparta(self, repo: AuditCsvRepository, tmp_path: Path) -> None:
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
        otro = AuditCsvRepository(
            audit_csv_path=tmp_path / "audit.csv", columnas_auditoria=_COLUMNS, logger=logging.getLogger("test")
        )
        otro.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=2, elapsed=0.1)

        assert list(tmp_path.glob("audit.invalid-*")) == []
        assert otro.leer_auditoria(usar_cache=False)["total_filas"].tolist() == [1, 2]

    def test_directorio_borrado_a_mitad_se_recrea(self, tmp_path: Path) -> None:
        # QW-2: ya no se hace mkdir en cada escritura; un FileNotFoundError crea el directorio y reintenta.
        csv_path = tmp_path / "sub" / "audit.csv"
        repo = AuditCsvRepository(
            audit_csv_path=csv_path, columnas_auditoria=_COLUMNS, logger=logging.getLogger("test")
        )
        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
        shutil.rmtree(tmp_path / "sub")

        repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=2, elapsed=0.1)

        df = repo.leer_auditoria(usar_cache=False)
        assert list(df.columns) == _COLUMNS
        assert df["total_filas"].tolist() == [2]

    def test_lock_se_resuelve_una_vez_por_ruta(self, repo: AuditCsvRepository) -> None:
        # QW-2: Path.resolve() (en _get_file_lock) costaba ~70 µs por escritura en Windows.
        # El código vive en util_bbdd.audit.legacy_csv desde la sesión 2026-10-02c: se espía allí.
        with patch("util_bbdd.audit.legacy_csv.path_lock", wraps=_get_file_lock) as spy:
            for _ in range(5):
                repo.registrar_operacion(tabla="t", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=0.1)
        assert spy.call_count == 1

    def test_cambiar_ruta_usa_el_lock_y_el_fichero_nuevos(self, tmp_path: Path) -> None:
        manager = AuditManager(audit_csv_path=tmp_path / "a.csv")
        manager.registrar_operacion("t", "sqlite", "INSERT", 1, 0.1)
        manager.audit_csv_path = tmp_path / "otro" / "b.csv"

        manager.registrar_operacion("t", "sqlite", "INSERT", 2, 0.1)

        assert manager._repository._lock is _get_file_lock(tmp_path / "otro" / "b.csv")
        assert len(manager.leer_auditoria(usar_cache=False)) == 1
        assert manager.leer_auditoria(usar_cache=False)["total_filas"].tolist() == [2]

    def test_fichero_con_datos_no_repite_cabecera(self, populated_repo: AuditCsvRepository, tmp_path: Path) -> None:
        lines = (tmp_path / "audit.csv").read_text(encoding="utf-8").splitlines()
        assert lines.count("\t".join(_COLUMNS)) == 1
        assert len(lines) == 4


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

    def test_escritura_de_otra_instancia_invalida_la_cache(self, tmp_path: Path) -> None:
        # H6 (audit-code 2026-09-25): la caché solo se invalidaba con las escrituras propias; con varias instancias
        # sobre el mismo CSV (ParallelBulkLoader) una lectura devolvía datos de hasta cache_ttl_seconds de antigüedad.
        lector = AuditManager(audit_csv_path=tmp_path / "audit.csv")
        escritor = AuditManager(audit_csv_path=tmp_path / "audit.csv")
        lector.registrar_operacion("t", "sqlite", "INSERT", 1, 0.1)
        assert len(lector.leer_auditoria()) == 1

        escritor.registrar_operacion("t", "sqlite", "INSERT", 2, 0.1)

        assert lector.leer_auditoria()["total_filas"].tolist() == [1, 2]

    def test_cache_se_reutiliza_si_el_fichero_no_cambia(self, populated_repo: AuditCsvRepository) -> None:
        populated_repo.leer_auditoria()
        with patch("util_bbdd.audit.legacy_csv.pd.read_csv") as read_csv:
            assert len(populated_repo.leer_auditoria()) == 3
        read_csv.assert_not_called()

    def test_fichero_borrado_invalida_la_cache(self, populated_repo: AuditCsvRepository, tmp_path: Path) -> None:
        populated_repo.leer_auditoria()
        (tmp_path / "audit.csv").unlink()
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

    def test_operacion_mas_lenta(self, service: AuditAnalyticsService) -> None:
        stats = service.obtener_estadisticas()
        assert stats["operacion_mas_lenta"] == "DELETE"

    def test_operacion_mas_lenta_en_empate_es_la_primera(self, populated_repo: AuditCsvRepository) -> None:
        populated_repo.registrar_operacion(tabla="users", motor="sqlite", operacion="INSERT", rowcount=1, elapsed=8.0)
        service = AuditAnalyticsService(repository=populated_repo, logger=logging.getLogger("test"))

        assert service.obtener_estadisticas()["operacion_mas_lenta"] == "DELETE"

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

    def test_umbral_igual_al_tiempo_queda_fuera_en_los_dos_filtros(self, service: AuditAnalyticsService) -> None:
        # La fila de 0,5 s cae justo en el umbral: ninguno de los dos la cuenta (hasta 3.0.3 filtrar_multiple sí)
        assert service.obtener_operaciones_lentas(umbral_segundos=0.5)["tiempo_seg"].tolist() == [8.0]
        assert service.filtrar_multiple(umbral_tiempo=0.5)["tiempo_seg"].tolist() == [8.0]

    def test_umbral_por_debajo_del_tiempo_lo_incluye_en_los_dos_filtros(self, service: AuditAnalyticsService) -> None:
        assert sorted(service.obtener_operaciones_lentas(umbral_segundos=0.4)["tiempo_seg"]) == [0.5, 8.0]
        assert sorted(service.filtrar_multiple(umbral_tiempo=0.4)["tiempo_seg"]) == [0.5, 8.0]

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

    def test_columnas_auditoria_es_de_solo_lectura(self, manager: AuditManager) -> None:
        # H7 (audit-code 2026-09-25): el setter cambiaba la cabecera pero las filas seguían teniendo 7 columnas.
        # U-8.6 (5.0.0, D8-8): el setter obsoleto se retira.
        columnas = list(manager.columnas_auditoria)
        with pytest.raises(AttributeError):
            manager.columnas_auditoria = _COLUMNS  # type: ignore[misc]
        assert manager.columnas_auditoria == columnas

    def test_ruta_inaccesible_lanza_audit_config_error_compatible_con_value_error(self, tmp_path: Path) -> None:
        # H8 (audit-code 2026-09-25): antes ValueError fuera de la jerarquía AuditError.
        (tmp_path / "fichero").write_text("no es un directorio", encoding="utf-8")
        with pytest.raises(AuditConfigError, match="No se puede acceder") as info:
            AuditManager(audit_csv_path=tmp_path / "fichero" / "sub" / "audit.csv")
        assert isinstance(info.value, ValueError)

    def test_registrar_sin_path_avisa_una_sola_vez(self, caplog: pytest.LogCaptureFixture) -> None:
        # QW-3 (P-11): antes, un WARNING por operación.
        manager = AuditManager(audit_csv_path=None)
        with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk.audit"):
            for _ in range(3):
                manager.registrar_operacion("t", "sqlite", "INSERT", 1, 0.1)
        assert [r.getMessage() for r in caplog.records].count("⚠️ Auditoría deshabilitada: audit_csv_path es None") == 1

    def test_registrar_no_emite_info_por_operacion(
        self, manager: AuditManager, caplog: pytest.LogCaptureFixture
    ) -> None:
        # QW-3 (P-11): "registrado en auditoría" y "Caché limpiado" pasan a DEBUG.
        with caplog.at_level(logging.INFO, logger="util_bbdd.bulk.audit"):
            manager.registrar_operacion("t", "sqlite", "INSERT", 1, 0.1)
        assert caplog.records == []

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

    def test_filtrar_por_operacion(self, populated_manager: AuditManager) -> None:
        df = populated_manager.filtrar_por_operacion("INSERT")
        assert len(df) == 1

    def test_obtener_operaciones_lentas(self, populated_manager: AuditManager) -> None:
        df = populated_manager.obtener_operaciones_lentas(umbral_segundos=0.3)
        assert len(df) == 1
