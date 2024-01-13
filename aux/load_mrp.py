import pandas as pd
import sys
import pickle
import subprocess
import os
def run_mrp_script(map_file_name, meta_var_filename, gb_path, typeofanalysis):
    cmd = [
        "python", "mrp/mrp.py",
        "--sigma_m_types", "sigma_m_var",
        "--file", map_file_name,
        "--build", "hg38",
        "--R_var", "independent", "similar",
        "--metadata", meta_var_filename,
        "--variants", "pav", "ptv",
        "--se_thresh", "1000000000000000000",
        "--out_filename", os.path.basename(gb_path) + "_" + typeofanalysis,
        "--out_folder", "/scratch/groups/mrivas/mrpout_genebass/"
    ]

    # Run the command
    subprocess.run(cmd)


def load_mrp_df(filename):
    # Load Pickle file
    return pd.read_pickle(filename)

def perform_analysis(mrp_df, gb_path, typeofanalysis):
    # Placeholder for analysis logic
    #Read in files, process, generate map file and then run MRP from Jupyter 
    if typeofanalysis == "ultrarare":
        prop_thr = 0.6
    else:
        prop_thr = 0
    gb_df = pd.read_csv(gb_path, sep='\t', compression='gzip')
    if typeofanalysis == "ultrarare":
        gb_filtered_df = gb_df[~gb_df['annotation'].isin(['LC', 'NA', 'synonymous']) & (gb_df['AC'] <= 5)]
    elif typeofanalysis == "pav":
        gb_filtered_df = gb_df[~gb_df['annotation'].isin(['LC', 'NA', 'synonymous']) & (gb_df['AF'] <= .01)]
    elif typeofanalysis == "missenseonly":
        gb_filtered_df = gb_df[~gb_df['annotation'].isin(['LC', 'NA', 'synonymous' , 'pLoF']) & (gb_df['AF'] <= .01)]
    elif typeofanalysis == "alphamissense" or typeofanalysis == "alphamissensebenign":
        # Load the AlphaMissense_hg38.tsv.gz file
        alpha_missense_df = pd.read_csv('AlphaMissense_hg38.tsv.gz', sep='\t', compression='gzip', skiprows = 3)
        gb_filtered_df = gb_df[~gb_df['annotation'].isin(['LC', 'NA', 'synonymous' , 'pLoF']) & (gb_df['AF'] <= .01)]
    # Processing 'locus' to get '#CHROM' and 'POS'
    gb_filtered_df['#CHROM'] = gb_filtered_df['locus'].apply(lambda x: x.split(':')[0].replace('chr', ''))
    gb_filtered_df['#CHROM'] = gb_filtered_df["#CHROM"].astype(str)
    gb_filtered_df['POS'] = gb_filtered_df['locus'].apply(lambda x: x.split(':')[1])
    # Convert to string if necessary (adjust as per your data types)
    gb_filtered_df['POS'] = gb_filtered_df['POS'].astype(str)
    mrp_df['pos'] = mrp_df['pos'].astype(str)
    mrp_df['chr'] = mrp_df['chr'].astype(str)
    # Merging DataFrames
    gb_filtered_df = pd.merge(gb_filtered_df, mrp_df, left_on=['#CHROM', 'POS'], right_on=['chr', 'pos'])
    gb_filtered_df = gb_filtered_df[gb_filtered_df['prob_0'] >= prop_thr]
    gb_filtered_df['REF'] = gb_filtered_df['markerID'].apply(lambda x: x.split('_')[1].split('/')[0])
    gb_filtered_df['ALT'] = gb_filtered_df['markerID'].apply(lambda x: x.split('_')[1].split('/')[1])
    if typeofanalysis == "alphamissense" or typeofanalysis == "alphamissensebenign":
        # Filter for likely_pathogenic variants
        if typeofanalysis == "alphamissense":
            likely_pathogenic_df = alpha_missense_df[alpha_missense_df['am_class'] == 'likely_pathogenic']
        elif typeofanalysis == "alphamissensebenign":
            likely_pathogenic_df = alpha_missense_df[alpha_missense_df['am_class'] == 'likely_benign']
        # Assuming gb_filtered_df is your existing DataFrame
        # Merge with gb_filtered_df on the specified columns
        likely_pathogenic_df = likely_pathogenic_df[['#CHROM','POS','REF','ALT']]
        likely_pathogenic_df.drop_duplicates(inplace=True)
        likely_pathogenic_df['#CHROM'] = likely_pathogenic_df['#CHROM'].apply(lambda x: x.replace('chr',''))
        likely_pathogenic_df['POS'] = likely_pathogenic_df['POS'].astype(str)
        likely_pathogenic_df['#CHROM'] = likely_pathogenic_df['#CHROM'].astype(str)
        gb_filtered_df = gb_filtered_df.merge(likely_pathogenic_df, left_on=['chr', 'pos', 'REF', 'ALT'], right_on=['#CHROM', 'POS', 'REF', 'ALT'])
        gb_filtered_df.drop_duplicates(inplace=True)
    gb_filtered_df['V'] = gb_filtered_df['chr'] + ':' + gb_filtered_df['pos'] + ':' + gb_filtered_df['REF'] + ':' + gb_filtered_df['ALT']
    meta_var_df = gb_filtered_df[['V', 'gene', 'annotation', 'AF']].copy()
    meta_var_df['ld_indep'] = True
    meta_var_df['pLI'] = "NA"
    meta_var_df['MPC'] = "NA"
    meta_var_df.rename(columns={
        'V': 'V',
        'gene': 'gene_symbol',
        'annotation': 'most_severe_consequence',
        'AF': 'maf'
    }, inplace=True)
    gb_filtered_df['P'] = gb_filtered_df["Pvalue"]
    # Keeping 'BETA', 'SE', and 'Pvalue'
    gb_filtered_df['#CHROM'] = gb_filtered_df['chr'] 
    gb_filtered_df['POS'] = gb_filtered_df['pos']
    gb_filtered_df = gb_filtered_df[['#CHROM', 'POS', 'REF', 'ALT', 'BETA', 'SE', 'P']]
    fileout = os.path.basename(gb_path).split('.')[0] + "_" + typeofanalysis + "_sumstat.tsv.gz"
    gb_filtered_df.to_csv("/scratch/groups/mrivas/genebassout/" + fileout, sep='\t', index=False, compression='gzip')
    fileout_pre = fileout.split('.')[0]  # Replace with the actual prefix
    map_file_name = "/scratch/groups/mrivas/genebassout/" + fileout_pre + ".map"
    meta_var_filename = "/scratch/groups/mrivas/genebassout/" + fileout_pre + ".meta.gz"

    with open(map_file_name, 'w') as f:
        f.write("path\tstudy\tpheno\tR_phen\n")
        f.write(f"/scratch/groups/mrivas/genebassout/{fileout}\tstudy1\tpheno1\tFALSE\n")  # Replace 'study1' and 'pheno1' with actual values
        meta_var_filename = fileout_pre + ".meta.gz"
        # Write meta_var_df to a tab-separated file
    meta_var_df.to_csv(meta_var_filename, sep='\t', index=False, compression="gzip")
    # Usage example

    print("Performing analysis...")

    # Example: Print the shape of the dataframe
    print(f"Shape of mrp_df: {mrp_df.shape}")

    # Example: Read additional data from gb_path if necessary
    gb_df = pd.read_csv(gb_path, sep='\t', compression='gzip')
    print(f"Shape of gb_df: {gb_df.shape}")

    run_mrp_script(map_file_name, meta_var_filename, gb_path, typeofanalysis)

    # More analysis code here...

if __name__ == "__main__":
    # Check if gb_path argument is provided
    if len(sys.argv) < 3:
        print("Usage: python load_mrp.py <gb_path> <typeofanalysis>")
        sys.exit(1)

    gb_path = sys.argv[1]
    print(f"GB Path: {gb_path}")
    typeofanalysis = sys.argv[2]
    # Load mrp_df
    mrp_df = load_mrp_df("mrp_df.pkl")

    # Continue your analysis with mrp_df and gb_path
    perform_analysis(mrp_df, gb_path, typeofanalysis)
