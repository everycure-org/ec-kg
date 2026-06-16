import polars as pl
import os 
import dotenv

# load env variables with your HF_TOKEN
dotenv.load_dotenv()

# loading datasets through Dataset repo instead of polars library directly to avoid rate-limits
df = pl.read_parquet("hf://datasets/everycure/kg-edges/data/edges/train-*.parquet", storage_options={"token": os.environ["HF_TOKEN"]})

# filter for PrimeKG, RoboKOP and RTX-KG2 and save each for duckdb extraction
df.filter(pl.col('upstream_data_source').list.contains('primekg')).write_parquet('data/primekg_edges.parquet')
df.filter(pl.col('upstream_data_source').list.contains('robokop')).write_parquet('data/robokop_edges.parquet')
df.filter(pl.col('upstream_data_source').list.contains('rtx_kg2')).write_parquet('data/rtx_kg2_edges.parquet')

# run SQL to calculate edge counts per source
import duckdb
query = """
WITH edges AS (
    SELECT
        'ROBOKOP' AS kg_name,
        subject AS subject_id,
        predicate,
        object AS object_id,
        primary_knowledge_source
    FROM 'data/robokop_edges.parquet'
    WHERE subject IS NOT NULL AND predicate IS NOT NULL AND object IS NOT NULL

    UNION ALL

    SELECT
        'RTX-KG2' AS kg_name,
        subject AS subject_id,
        predicate,
        object AS object_id,
        primary_knowledge_source
    FROM 'data/rtx_kg2_edges.parquet'
    WHERE subject IS NOT NULL AND predicate IS NOT NULL AND object IS NOT NULL

    UNION ALL

    SELECT
        'PrimeKG' AS kg_name,
        subject AS subject_id,
        predicate,
        object AS object_id,
        primary_knowledge_source
    FROM 'data/primekg_edges.parquet'
    WHERE subject IS NOT NULL AND predicate IS NOT NULL AND object IS NOT NULL
),
dedup AS (
    -- de-duplicate within each KG by edge_key
    SELECT DISTINCT
        kg_name,
        subject_id, predicate, object_id,
        primary_knowledge_source,
        subject_id || '␞' || predicate || '␞' || object_id AS edge_key
    FROM edges
)
SELECT
    kg_name,
    primary_knowledge_source,
    COUNT(DISTINCT edge_key) AS edge_count
FROM dedup
GROUP BY kg_name, primary_knowledge_source
ORDER BY kg_name, edge_count DESC
"""

res = duckdb.sql(query)
print(res)
res.write_parquet('data/edge_counts_by_source.parquet')
