# Manejo de errores y reintentos

result = loader.load(...)
if result.partition_errors:
    print(f"⚠️  {len(result.partition_errors)} particiones fallidas")
    # Reintentar manualmente o marcar para revisión manual
