
# README for process_phenotypes.py

## Overview
The `process_phenotypes.py` script is designed to read and process phenotype data stored in a Hail MatrixTable format. This script is specifically tailored for use with data from genebass.org.

## Prerequisites
Before running the script, ensure that you have the following prerequisites:

1. Python installed on your system.
2. Hail library installed. You can install Hail using `pip install hail`.
3. Access to the dataset `/scratch/groups/mrivas/variant_results.mt` which should be in Hail MatrixTable format.

## Usage
The script can be executed from the command line by specifying the start and end index for the phenotypes to process. These indices correspond to the range of phenotypes within the data you wish to process.

```bash
python process_phenotypes.py [start_index] [end_index]
```

Replace `[start_index]` and `[end_index]` with integer values representing the range of phenotypes.

## Script Functionality
1. **Initialization:**
   - The script initializes a Hail context to work with Hail's MatrixTable data structure.

2. **Reading the Matrix Table:**
   - The script reads a MatrixTable from the specified location (`/scratch/groups/mrivas/variant_results.mt`).

3. **Aggregating Phenotype Codes:**
   - It aggregates phenotype codes from the MatrixTable columns and sorts them.

4. **Processing Phenotypes:**
   - The script processes a subset of phenotypes based on the provided start and end indices.
   - If a file for a specific phenotype already exists in the output directory (`/scratch/groups/mrivas/genebassout/`), that phenotype is skipped.
   - For each phenotype, it filters the MatrixTable, converts it to a table, and then exports the data to a file in TSV format with GZIP compression.

## Output
- The output files are saved in the directory `/scratch/groups/mrivas/genebassout/`.
- Each file is named after its phenotype code and saved in TSV format with GZIP compression (`.genebass.tsv.gz`).

## Notes
- Ensure you have sufficient permissions to read the input data and write to the output directory.
- The script is intended for batch processing of phenotype data and might require modifications for different datasets or specific use cases.

## load_mrp.py Script

### Overview
`load_mrp.py` is a Python script for loading and processing genotype-phenotype data. It integrates with external scripts and performs customized data analysis based on user-defined criteria.

### Prerequisites
- Python environment with necessary libraries installed (`pandas`, `subprocess`, `os`, etc.).
- The required data files and the `mrp.py` script must be accessible in the specified paths.

### Usage
Execute the script from the command line by providing the genebass file path and the type of analysis to be performed:

```bash
python load_mrp.py [gb_path] [typeofanalysis]
```

Replace `[gb_path]` with the path to the genebass data file and `[typeofanalysis]` with the type of analysis (e.g., 'ultrarare', 'pav', 'missenseonly', 'alphamissense', etc.).

### Script Functionality
1. **`perform_analysis` Function:**
   - Processes the genebass data file (`gb_path`) and performs analysis based on the type specified in `typeofanalysis`.
   - The script applies various filters to the data, processes it, and generates summary statistics and metadata files.

2. **`run_mrp_script` Function:**
   - Constructs and executes a command to run the `mrp.py` script with the appropriate parameters.
   - The parameters include file paths, genetic variants, thresholds, and output settings.

3. **Data Processing:**
   - The script reads and filters data based on annotations, allele frequency, and other criteria specific to the analysis type.
   - Merges data from different sources and prepares it for further analysis.

4. **Output:**
   - Generates summary statistics and metadata files in the specified output directory.
   - The output includes various genetic and phenotypic data points, like chromosome, position, reference and alternate alleles, etc.

### Notes
- Ensure the paths and filenames in the script match the structure and format of your data and directory.
- The script might require customization for different datasets or specific analytical requirements.
