import os, duckdb, pandas as pd

db_path = os.path.join('data', 'warehouse', 'products.duckdb')
con = duckdb.connect(db_path)

print('--- pipeline_runs (all) ---')
print(con.execute('SELECT * FROM pipeline_runs ORDER BY run_id').fetchdf())

print('\n--- standardized_products per run ---')
print(con.execute('SELECT last_run_id as run_id, COUNT(*) as product_cnt FROM standardized_products GROUP BY last_run_id ORDER BY run_id').fetchdf())

print('\n--- quarantine_records per run ---')
print(con.execute('SELECT run_id, COUNT(*) as quarantine_cnt FROM quarantine_records GROUP BY run_id ORDER BY run_id').fetchdf())

print('\n--- duplicate quarantine entries within a run (run_id, supplier_id, supplier_sku) >1 ---')
dup_q = con.execute('''
SELECT run_id, supplier_id, supplier_sku, COUNT(*) as cnt
FROM quarantine_records
GROUP BY run_id, supplier_id, supplier_sku
HAVING COUNT(*) > 1
''').fetchdf()
print(dup_q)

print('\n--- duplicate standardized product IDs across runs ---')
dup_sp = con.execute('''
SELECT canonical_product_id, COUNT(DISTINCT last_run_id) as run_cnt
FROM standardized_products
GROUP BY canonical_product_id
HAVING COUNT(DISTINCT last_run_id) > 1
''').fetchdf()
print(dup_sp)
