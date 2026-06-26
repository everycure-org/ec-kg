# venv:
#     uv venv
#     uv pip install -r requirements.txt
#     source .venv/bin/activate

knowledge_source_aggregation:
	python technical_validation/knowledge_source_aggregation/kg_source_aggregation.py

novel_context: sample_pairs generate_sop analyse_sop

sample_pairs:
	python technical_validation/novel_context/01_sample_pairs.py

analyse_sop:
	python technical_validation/novel_context/03_analyse.py

analyse_metapath:
	python technical_validation/novel_context/04_metapath_analysis.py
	python technical_validation/novel_context/05_visualize_metapath_analysis.py

generate_sop:
	python technical_validation/novel_context/02_calculate_sop.py --kg_name primekg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/primekg
	python technical_validation/novel_context/02_calculate_sop.py --kg_name robokop --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/robokop
	python technical_validation/novel_context/02_calculate_sop.py --kg_name rtx_kg2 --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/rtx_kg2
	python technical_validation/novel_context/02_calculate_sop.py --kg_name integrated_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/integrated_kg
	python technical_validation/novel_context/02_calculate_sop.py --kg_name filtered_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/filtered_kg

# NOTE: this command assumes that modelling results and outputs are stored in GCS or paths specified in the analyse_output.py script
ml_validation:
	python technical_validation/ml_validation/analyse_output.py