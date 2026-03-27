venv:
	uv venv
	uv pip install -r requirements.txt
	source .venv/bin/activate

default: venv sample_pairs generate_sop

sample_pairs:
	python src/01_sample_pairs.py

generate_sop:
	python src/02_calculate_sop.py --kg_name primekg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/primekg
	python src/02_calculate_sop.py --kg_name robokop --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/robokop
	python src/02_calculate_sop.py --kg_name rtx_kg2 --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/rtx_kg2
	python src/02_calculate_sop.py --kg_name integrated_kg --kg_path /Users/piotrkaniewski/work/ec-kg-analysis/data/integrated_kg