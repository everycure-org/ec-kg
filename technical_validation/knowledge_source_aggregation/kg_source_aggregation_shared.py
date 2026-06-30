"""Script used to calculate top primary knowledge sources for each upstream KG in EC-KG"""
import polars as pl
from datasets import load_dataset, Dataset
import duckdb
import dotenv

# load env variables with your HF_TOKEN
dotenv.load_dotenv()

# # loading datasets through Dataset repo instead of polars library directly to avoid rate-limits
# df = Dataset.to_polars(load_dataset("everycure/kg-edges")['train'])

# # filter for PrimeKG, RoboKOP and RTX-KG2 and save each for duckdb extraction
# df.filter(pl.col('upstream_data_source').list.contains('primekg')).write_parquet('data/primekg_edges.parquet')
# df.filter(pl.col('upstream_data_source').list.contains('robokop')).write_parquet('data/robokop_edges.parquet')
# df.filter(pl.col('upstream_data_source').list.contains('rtxkg2')).write_parquet('data/rtx_kg2_edges.parquet')

# run SQL to calculate edge counts per source
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

), dups AS (
    SELECT
        kg_name,
        primary_knowledge_source,
        count(*) as dup_count

    FROM edges
    group by kg_name, primary_knowledge_source

)
SELECT
    primary_knowledge_source,
    SUM(dup_count) AS total_dup_count
FROM (
    SELECT
        kg_name,
        primary_knowledge_source,
        dup_count,
        COUNT(*) OVER (
            PARTITION BY primary_knowledge_source
        ) AS source_count
    FROM dups
) t
WHERE source_count > 1
GROUP BY primary_knowledge_source
ORDER BY
    total_dup_count DESC,
    primary_knowledge_source DESC;
"""

res = duckdb.sql(query)
print(res)
res.write_parquet('data/edge_counts_by_source_shared.parquet')
