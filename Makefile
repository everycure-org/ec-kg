# venv:
# 	uv venv
# 	uv pip install -r requirements.txt
# 	source .venv/bin/activate

default: sample_pairs generate_sop analyse_sop

sample_pairs:
	python technical_validation/01_sample_pairs.py

analyse_sop:
	python technical_validation/03_analyse.py

generate_sop:
	python technical_validation/02_calculate_sop.py --kg_name primekg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/primekg
	python technical_validation/02_calculate_sop.py --kg_name robokop --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/robokop
	python technical_validation/02_calculate_sop.py --kg_name rtx_kg2 --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/rtx_kg2
	python technical_validation/02_calculate_sop.py --kg_name integrated_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/integrated_kg
	python technical_validation/02_calculate_sop.py --kg_name filtered_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/filtered_kg