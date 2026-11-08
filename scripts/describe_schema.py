import duckdb, os, pandas as pd
db_path = os.path.join('data','warehouse','products.duckdb')
con = duckdb.connect(db_path)
print('--- pipeline_runs schema ---')
print(con.execute('DESCRIBE pipeline_runs').fetchdf())
print('\n--- standardized_products schema ---')
print(con.execute('DESCRIBE standardized_products').fetchdf())
print('\n--- quarantine_records schema ---')
print(con.execute('DESCRIBE quarantine_records').fetchdf())
