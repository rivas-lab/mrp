
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
