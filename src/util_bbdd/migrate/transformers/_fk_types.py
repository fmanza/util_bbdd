"""Paso común tras transformar: cada columna FK toma el tipo destino de la columna que referencia (G28 de util_bbdd_web).

Cada transformer convierte las columnas de una en una, sin ver la tabla referenciada, y una FK puede acabar con otro
tipo que su columna referenciada: Oracle ``INT`` (``NUMBER`` sin precisión) da ``INT(11)`` en la PK (autoincremental)
y ``DOUBLE`` en la FK (``number_fallback``). MariaDB y MySQL rechazan esa FK a mitad de ``execute()``; el resto de
destinos la acepta o no según el par de tipos.

Copiar el tipo no pierde datos: los valores de una FK validada son valores de la columna referenciada. Solo se
alinean las FK cuya tabla referenciada está en el plan (las externas no tienen tipo conocido).
"""

from __future__ import annotations

import re

from ..ir.models import CanonicalColumn, CanonicalTable, MigrationWarning

#: Ancho de visualización de los enteros de MySQL/MariaDB (``INT(11)``): no cambia el tipo.
_INT_WIDTH = re.compile(r"^(TINYINT|SMALLINT|MEDIUMINT|INT|INTEGER|BIGINT)\(\d+\)")


def _comparable(target_type: str) -> str:
    """Tipo comparable: mayúsculas, espacios simples y sin el ancho de visualización de los enteros."""
    return _INT_WIDTH.sub(r"\1", " ".join(target_type.upper().split()))


def _index(tables: list[CanonicalTable]) -> dict[str, tuple[CanonicalTable, dict[str, CanonicalColumn]]]:
    """Tablas por nombre destino y original (en minúsculas), con sus columnas indexadas igual."""
    index: dict[str, tuple[CanonicalTable, dict[str, CanonicalColumn]]] = {}
    for table in tables:
        columns: dict[str, CanonicalColumn] = {}
        for column in table.columns:
            columns.setdefault(column.original_name.lower(), column)
            columns.setdefault(column.name.lower(), column)
        for key in (table.original_name.lower(), table.name.lower()):
            index.setdefault(key, (table, columns))
    return index


def align_fk_types(tables: list[CanonicalTable]) -> None:
    """Da a cada columna FK el ``target_type`` de la columna referenciada; avisa en ``table.warnings``.

    - Tipo distinto: la columna FK toma el de la referenciada (también su ``ddl_comment`` y sus avisos ``TYPE`` de
      nivel ``WARNING`` desaparecen, porque describían el tipo descartado) y aviso ``FK_TYPE_ALIGNED`` (``INFO``).
      En una cadena (A → B → C) manda el tipo del final.
    - Sin alineación posible (columna referenciada inexistente u omitida, o dos FK de la misma columna hacia tipos
      distintos): aviso ``FK_TYPE_UNRESOLVED`` (``ERROR``), que impide ``MigrationPlan.execute``.

    Args:
        tables: Tablas ya transformadas al destino (se modifican en el sitio).
    """
    index = _index(tables)

    def referenced(table: CanonicalTable, column: CanonicalColumn) -> list[tuple[str, str, CanonicalColumn | None]]:
        """``(tabla, columna, columna referenciada o None)`` de cada FK interna de ``table`` sobre ``column``."""
        result = []
        names = {column.name.lower(), column.original_name.lower()}
        for fk in table.foreign_keys:
            if fk.is_external or fk.ref_table.lower() not in index:
                continue
            _, ref_columns = index[fk.ref_table.lower()]
            for own, ref in zip(fk.columns, fk.ref_columns, strict=False):
                if own.lower() in names:
                    result.append((fk.ref_table, ref, ref_columns.get(ref.lower())))
        return result

    def final_type(table: CanonicalTable, column: CanonicalColumn, seen: set[int]) -> str:
        """Tipo al final de la cadena de FK que empieza en ``column`` (un ciclo se corta en la columna repetida)."""
        if id(column) in seen:
            return column.target_type
        seen.add(id(column))
        for ref_table, _, ref_column in referenced(table, column):
            if ref_column is not None and not ref_column.omit:
                return final_type(index[ref_table.lower()][0], ref_column, seen)
        return column.target_type

    for table in tables:
        fk_columns = {own.lower() for fk in table.foreign_keys for own in fk.columns}
        for column in table.columns:
            if column.omit or (
                column.name.lower() not in fk_columns and column.original_name.lower() not in fk_columns
            ):
                continue
            references = referenced(table, column)
            if not references:
                continue
            problem = next(
                (
                    f"la columna referenciada '{ref_table}.{ref}' "
                    + ("no existe en el plan" if ref_column is None else "se omite en el destino")
                    for ref_table, ref, ref_column in references
                    if ref_column is None or ref_column.omit
                ),
                None,
            )
            types = {
                _comparable(final_type(index[ref_table.lower()][0], ref_column, {id(column)})): (ref_table, ref)
                for ref_table, ref, ref_column in references
                if ref_column is not None and not ref_column.omit
            }
            if problem is None and len(types) > 1:
                problem = (
                    "referencia columnas de tipos distintos ("
                    + ", ".join(f"{ref_table}.{ref}: {target}" for target, (ref_table, ref) in sorted(types.items()))
                    + ")"
                )
            if problem is not None:
                table.warnings.append(
                    MigrationWarning(
                        table=table.name,
                        column=column.name,
                        category="FOREIGN_KEY",
                        target_type=column.target_type,
                        code="FK_TYPE_UNRESOLVED",
                        message=(
                            f"Tabla '{table.name}': la columna FK '{column.name}' no puede tomar el tipo de su columna "
                            f"referenciada: {problem}. El destino rechazaría la FK; revisar el origen."
                        ),
                        severity="ERROR",
                    )
                )
                continue
            ref_table, ref = next(iter(types.values()))
            ref_column = index[ref_table.lower()][1][ref.lower()]
            target = final_type(index[ref_table.lower()][0], ref_column, {id(column)})
            if _comparable(target) == _comparable(column.target_type):
                continue
            previous = column.target_type
            column.target_type = target
            column.ddl_comment = None
            column.warnings = [w for w in column.warnings if not (w.category == "TYPE" and w.severity == "WARNING")]
            table.warnings.append(
                MigrationWarning(
                    table=table.name,
                    column=column.name,
                    category="FOREIGN_KEY",
                    target_type=target,
                    source_type=column.source_type,
                    code="FK_TYPE_ALIGNED",
                    message=(
                        f"Tabla '{table.name}': la columna FK '{column.name}' toma el tipo {target} de "
                        f"'{ref_table}.{ref}' en lugar de {previous}; el destino exige el mismo tipo en los dos lados."
                    ),
                    severity="INFO",
                )
            )


__all__: list[str] = ["align_fk_types"]
