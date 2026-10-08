# Context Snapshot — 2026-10-07

## Workspace
- Path: c:\Desarrollo\python\libs\util_bbdd
- Current version: 0.35.3
- Target version: 0.35.4

## Problem Statement
MariaDB driver v1.1.14 executes init_command during mariadb.ConnectionPool() creation, not after.
This causes SQL syntax errors when init_command is passed as pool parameter.

## Root Cause Analysis
- Driver attempts: `pool = mariadb.ConnectionPool(init_command="SET NAMES utf8mb4", ...)`
- Expected: Pool created, then init_command executed in each get_connection()
- Actual: Driver tries to execute SET NAMES during pool instantiation, causing error
- Workaround: Extract init_command before pool creation, execute manually per connection

## Current Architecture
- pool_connection_mariadb.py creates mariadb.ConnectionPool with sanitized_conn_params
- ConnectionFactory creates pool via pool_connection_mariadb.MariaDBPoolConnection
- init_command currently passed directly to pool params (broken in v1.1.14)

## Solution
1. Extract init_command to self._pending_init_command before pool creation
2. Remove from pool_params dict
3. Execute manually in get_connection() after obtaining connection

## Files to Modify
- config.py: init_command default value (simplified)
- pool_connection_mariadb.py: extraction logic + manual execution
- database_types.json: JSON schema update
- test_mariadb_driver_connection.py: test assertion update
- 4 doc files: example updates
- CHANGELOG.md: new entry for 0.35.4
