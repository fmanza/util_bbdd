# Sincronizar secuencias PK tras inserción
from util_bbdd.bulk import bulk_crud

# Post-load: resincronizar auto_increment/sequence si es necesario
bcm = bulk_crud(target_engine)
pk_results = bcm.sync_pk_sequences(tables=["sales_data"])
for r in pk_results:
    print(f"{r.table_name}.{r.column_name}: {r.status}")
