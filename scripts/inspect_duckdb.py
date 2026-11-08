import os, duckdb

db_path = os.path.join('data', 'warehouse', 'products.duckdb')
con = duckdb.connect(db_path)

print('Tables:')
print(con.execute('SHOW TABLES').fetchdf())

print('\nQuarantine count:')
print(con.execute('SELECT COUNT(*) FROM quarantine_records').fetchone()[0])

print('\nStandardized count:')
print(con.execute('SELECT COUNT(*) FROM standardized_products').fetchone()[0])

print('\nPipeline runs:')
print(con.execute('SELECT run_id, canonical_product_count, quarantine_count FROM pipeline_runs ORDER BY run_id').fetchdf())

# Show per-run counts for standardized_products and quarantine
print('\nStandardized products per run:')
print(con.execute('SELECT last_run_id, COUNT(*) AS cnt FROM standardized_products GROUP BY last_run_id ORDER BY last_run_id').fetchdf())

print('\nQuarantine records per run:')
print(con.execute('SELECT run_id, COUNT(*) AS cnt FROM quarantine_records GROUP BY run_id ORDER BY run_id').fetchdf())
