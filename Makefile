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
	python technical_validation/novel_context/05_visualize_metapath_analysis.py --input /Users/piotrkaniewski/work/ec-kg-analysis/technical_validation/metapath_diversity.csv
	python technical_validation/novel_context/06_visualize_intermediate_nodes.py

generate_sop:
	python technical_validation/novel_context/02_calculate_sop.py --kg_name primekg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/primekg
	python technical_validation/novel_context/02_calculate_sop.py --kg_name robokop --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/robokop
	python technical_validation/novel_context/02_calculate_sop.py --kg_name rtx_kg2 --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/rtx_kg2
	python technical_validation/novel_context/02_calculate_sop.py --kg_name integrated_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/integrated_kg
	python technical_validation/novel_context/02_calculate_sop.py --kg_name filtered_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/filtered_kg

FIGURE_8_DIR := technical_validation/ml_validation/figure_8_ml_validation
FIGURE_8_OUTCOMES := $(FIGURE_8_DIR)/outcomes

# Reproduces the revised Figure 8a statistics and PDF.
ml_validation: figure_8a

# Requires MATRIX_ROOT to contain ec/, prime/, robokop/, and rtx/ matrix fold directories.
figure_8_extract:
	@test -n "$(MATRIX_ROOT)" || (echo "Set MATRIX_ROOT to the downloaded Figure 8 matrix directory"; exit 1)
	uv run python $(FIGURE_8_DIR)/extract_outcomes.py --matrix-root $(MATRIX_ROOT) --output-dir $(FIGURE_8_OUTCOMES)

figure_8_stats:
	uv run python $(FIGURE_8_DIR)/statistical_analysis.py \
		--classification-outcomes $(FIGURE_8_OUTCOMES)/figure_8_classification_outcomes.parquet \
		--estimates-output $(FIGURE_8_OUTCOMES)/figure_8a_f1_estimates.csv \
		--comparisons-output $(FIGURE_8_OUTCOMES)/figure_8a_f1_comparisons.csv

figure_8a: figure_8_stats
	uv run python $(FIGURE_8_DIR)/generate_figure_8a.py \
		--estimates $(FIGURE_8_OUTCOMES)/figure_8a_f1_estimates.csv \
		--comparisons $(FIGURE_8_OUTCOMES)/figure_8a_f1_comparisons.csv \
		--output $(FIGURE_8_DIR)/figure_8a_f1_bootstrap.pdf