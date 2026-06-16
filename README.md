# EC-KG analysis and usage

This repository contains complementary analysis code to the Every Cure KG publication. DOI and arxiv link to be added. 

![graphical-abstract](./assets/kg_paper_fig1_v2.drawio.png)

## EC-KG Usage 

If you are interested in using EC-KG, please see our [hugging face org](https://huggingface.co/datasets/everycure) - this is where you can find information on EC-KG [nodes](https://huggingface.co/datasets/everycure/kg-nodes), [edges](https://huggingface.co/datasets/everycure/kg-edges) as well as supplementary [drug list](https://huggingface.co/datasets/everycure/drug-list), [disease list](https://huggingface.co/datasets/everycure/disease-list) and [indications list](https://huggingface.co/datasets/everycure/indications-list). 

You can load EC-KG nodes and edges with a few lines of code with help of HF Datasets library:
```
from datasets import load_dataset

edges_ds = load_dataset("everycure/kg-edges")
nodes_ds = load_dataset("everycure/kg-nodes")
```

## Setup
```
make venv
```
## EC-KG Construction
For code constructing EC-KG, see [MATRIX repo](https://github.com/everycure-org/matrix). 


## Technical Validation
Below code (wrapped in Makefile for ease of use) can be used to reproduce the analysis used in the technical validation section of the paper. Note that the computations performed are computationally intensive and require at least 32 GB of RAM, with 4-hop SOP calculation requiring up to 512 GB for extracting paths from EC-KG.

### Emergence of Novel Context
To reproduce the analysis for Emergence of Novel Context section, run:
```
make emergence_novel_context
```

### Knowledge Source Aggregation
```
make knowledge_source_aggregation
```

