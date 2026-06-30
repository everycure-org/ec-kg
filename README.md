# EC-KG: Every Cure Knowledge Graph, a Unified Biomedical Knowledge Graph for Drug Repurposing

This repository contains complementary analysis code to the Every Cure KG publication. 

DOI to the datasets published: doi.org/10.5281/zenodo.20815441

Paper: to be added


![graphical-abstract](./assets/kg_paper_fig1_v2.drawio.png)

## EC-KG Usage 

If you are interested in using EC-KG, please see our [hugging face org](https://huggingface.co/datasets/everycure) - this is where you can find information on EC-KG [nodes](https://huggingface.co/datasets/everycure/kg-nodes), [edges](https://huggingface.co/datasets/everycure/kg-edges) as well as supplementary [drug list](https://huggingface.co/datasets/everycure/drug-list), [disease list](https://huggingface.co/datasets/everycure/disease-list) and [indications list](https://huggingface.co/datasets/everycure/indications-list). 

You can load EC-KG nodes and edges with a few lines of code with help of HF Datasets library:
```
from datasets import load_dataset

edges_ds = load_dataset("everycure/kg-edges")
nodes_ds = load_dataset("everycure/kg-nodes")
```
## EC-KG re-construction
If you want to reproduce EC-KG construction, see code constructing EC-KG, see [MATRIX repo](https://github.com/everycure-org/matrix). MATRIX pipeline can be used out of the box to re-construct KG by running a series of `make` commands:
```bash
uv venv
uv sync
make local_test # to see if pipeline works as expected
kedro run --pipeline data_engineering # to reconstruct
```
Detailed documentation how to use MATRIX pipeline can be found at https://docs.dev.everycure.org/getting_started/


## Technical Validation
Below code (wrapped in Makefile for ease of use) can be used to reproduce the analysis used in the technical validation section of the paper. Note that the computations performed are computationally intensive and require at least 32 GB of RAM, with 4-hop SOP calculation requiring up to 512 GB for extracting paths from EC-KG.

### Emergence of Novel Context
To reproduce the analysis for Emergence of Novel Context section, run:
```
make emergence_novel_context
```

### Knowledge Source Aggregation
To reproduce Knowledge Source Aggregation Analysis, run:
```
make knowledge_source_aggregation
```

### Machine Learning Validation
To reproduce the ML-based validation of computational drug repurposing use case, one needs to reproduce the KG re-construction and modelling run using [MATRIX modelling pipeline](https://github.com/everycure-org/matrix/tree/feat/kg-manuscript-model-run). 
0. Re-construct EC-KG using MATRIX pipeline using git sha `60369715eff704384189ce11a22c4a0cbc0b9f24`. This step is essential to ensure all datasets are aligned with the kedro data catalog, enabling MATRIX modelling pipeline running out of the box.
```bash
git checkout 60369715eff704384189ce11a22c4a0cbc0b9f24
kedro run --pipeline data_engineering 
``` 
1. Using [MATRIX pipeline](https://github.com/everycure-org/matrix), run `feature_modelling` pipeline for RTX-KG2 using git sha `5654eec23ca9662e168432614a7b40499a3cfb9f`:
```bash
git checkout 5654eec23ca9662e168432614a7b40499a3cfb9f
kedro run --pipeline feature_and_modelling
```
2. Using [MATRIX pipeline](https://github.com/everycure-org/matrix), run `feature_modelling` pipeline for PrimeKG using git sha `2d93853a2703b33c75ca535a8ec2c60407ce56e0`:
```bash
git checkout 2d93853a2703b33c75ca535a8ec2c60407ce56e0
kedro run --pipeline feature_and_modelling
```
3. Using [MATRIX pipeline](https://github.com/everycure-org/matrix), run `feature_modelling` pipeline for ROBOKOP using git sha `88d1c75ef534a02b2ac1ee3a808c057de601f8d9` 
```bash
git checkout 88d1c75ef534a02b2ac1ee3a808c057de601f8d9
kedro run --pipeline feature_and_modelling
```
4. Using [MATRIX pipeline](https://github.com/everycure-org/matrix), run `feature_modelling` pipeline for EC-KG using git sha `58ff055483c1fe1fb6f3ee57379729e4ac753e4d`
```bash
git checkout 58ff055483c1fe1fb6f3ee57379729e4ac753e4d
kedro run --pipeline feature_and_modelling
```

Once the modelling pipelines run to completion, the following makefile command can be executed to reproduce analysis present in the Technical Validation section:
```
make ml_validation
```
