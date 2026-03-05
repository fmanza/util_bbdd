# Changelog

Todos los cambios notables en este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- (próximos features)

## [0.1.0] - 2026-03-06

### Added
- Módulo `bulk_crud_audit`: CRUD masivo (insert/update/delete) desde DataFrames
- Sistema de auditoría automática en CSV con timestamps
- Factory para conexiones con pool singleton
- Validación de tipos por dialecto SQL (MySQL/Oracle/PostgreSQL)
- Gestión de metadatos con caché
- Documentación automática de BD (Word/Excel)
- Tests unitarios con pytest y cobertura
- Documentación en README y docstrings (Google style)

### Fixed
- Normalización de columnas según dialecto (Oracle: lower, MySQL: upper)
- Manejo de valores NULL en operaciones CRUD

[0.1.0]: https://github.com/tu_org/util_bbdd/releases/tag/v0.1.0
