#!/bin/bash
# Directory containing the files
DIRECTORY="/scratch/groups/mrivas/genebassout/"
# Directory where the output files are stored
OUTPUT_DIRECTORY="/scratch/groups/mrivas/mrpout_genebass/"

# Array of types of analysis
TYPES_OF_ANALYSIS=("ultrarare" "pav" "missenseonly")

# Iterate over files in the directory with the specified suffix
for FILE in ${DIRECTORY}*.genebass.tsv.gz; do
    # Extract the filename without path and suffix for job naming
    FILENAME=$(basename "$FILE" .genebass.tsv.gz)
    # Iterate over each type of analysis
    for TYPE in "${TYPES_OF_ANALYSIS[@]}"; do
        # Construct the output file name
	#/scratch/groups/mrivas/mrpout_genebass/study1_100009.genebass.tsv.gz_alphamissense_gene_maf_0.01_se_1e+18.tsv.gz
        OUTPUT_FILE="${OUTPUT_DIRECTORY}study1_${FILENAME}.genebass.tsv.gz_${TYPE}_gene_maf_0.01_se_1e+18.tsv.gz"
        
        # Debug: Print the file being checked
        echo "Checking for: $OUTPUT_FILE"

        # Check if the output file already exists
        if [ ! -f "$OUTPUT_FILE" ]; then
            # Submit a job if the file does not exist
            echo "Submitting job for $FILE with type $TYPE"
            sbatch -t 24:00:00 -p normal,mrivas,owners -N 1 --mem=64Gb -J "${FILENAME}_${TYPE}" --wrap="python load_mrp.py '$FILE' '$TYPE'"
        else
            echo "Output file already exists: $OUTPUT_FILE, skipping job submission."
        fi
    done
done
