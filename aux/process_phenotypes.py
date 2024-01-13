# process_phenotypes.py
import sys
import hail as hl
import os

def process_phenotypes(start_index, end_index):
    hl.init()

    # Read the matrix table
    mt = hl.read_matrix_table('/scratch/groups/mrivas/variant_results.mt')
    pheno_codes_set = mt.aggregate_cols(hl.agg.collect_as_set(mt.phenocode))

    # Convert the set to a list and sort it (optional, but often useful)
    pheno_codes_list = sorted(list(pheno_codes_set))

    # Process the subset of phenotypes using the list
    for pheno_code in pheno_codes_list[start_index:end_index]:
        if os.path.exists("/scratch/groups/mrivas/genebassout/" + pheno_code + ".genebass.tsv.gz"):
            print(pheno_code + " EXISTS, SKIPPING")
            continue
        subset_mt = mt.filter_cols(mt.phenocode == pheno_code)
        subset_table = subset_mt.entries()
        output_path = f'/scratch/groups/mrivas/genebassout/{pheno_code}.genebass.tsv.gz'
        subset_table.export(output_path, header=True)

if __name__ == "__main__":
    start_index = int(sys.argv[1])
    end_index = int(sys.argv[2])
    process_phenotypes(start_index, end_index)

