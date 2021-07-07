# Multiple Rare-variants and Phenotypes

This directory contains code and documentation for the [Multiple Rare-variants and Phenotypes method](https://www.biorxiv.org/content/10.1101/257162v5) by Venkataraman *et. al.*. The repository is maintained by Guhan Ram Venkataraman (GitHub: guhanrv).

## Script details and options

A full list of options can be obtained by running `python mrp_production.py -h`, and the output is replicated here for reference:

```{bash}
(base) user$ python mrp_production.py -h
usage: mrp_production.py [-h] --file MAP_FILE --metadata_path METADATA_PATH
                         [--R_study {independent,similar} [{independent,similar} ...]]
                         [--R_var {independent,similar} [{independent,similar} ...]]
                         [--M {variant,gene} [{variant,gene} ...]]
                         [--sigma_m_types {sigma_m_mpc_pli,sigma_m_var,sigma_m_1,sigma_m_005} [{sigma_m_mpc_pli,sigma_m_var,sigma_m_1,sigma_m_005} ...]]
                         [--variants {pcv,pav,ptv} [{pcv,pav,ptv} ...]]
                         [--maf_thresh MAF_THRESHES [MAF_THRESHES ...]]
                         [--se_thresh SE_THRESHES [SE_THRESHES ...]]
                         [--prior_odds PRIOR_ODDS_LIST [PRIOR_ODDS_LIST ...]]
                         [--p_value {farebrother,davies,imhof} [{farebrother,davies,imhof} ...]]
                         [--exclude EXCLUDE] [--filter_ld_indep]
                         [--out_folder OUT_FOLDER]
                         [--out_filename OUT_FILENAME]

MRP takes in several variables that affect how it runs.

  -h, --help            show this help message and exit
  --file MAP_FILE       path to tab-separated file containing list of: 
                                 summary statistic file paths,
                                 corresponding studies,
                                 phenotypes, and
                                 whether or not to use the file in R_phen generation.
                               
                                 format:
                                 
                                 path        study        pheno        R_phen
                                 /path/to/file1   study1    pheno1     TRUE
                                 /path/to/file2   study2    pheno1     FALSE
                                 
  --metadata_path METADATA_PATH
                        path to tab-separated file containing:
                                 variants,
                                 gene symbols,
                                 consequences,
                                 MAFs,
                                 and LD independence info.
                               
                                 format:
                                 
                                 V       gene_symbol     most_severe_consequence maf  ld_indep
                                 1:69081:G:C     OR4F5   5_prime_UTR_variant     0.000189471     False

optional arguments:
                                
  --R_study {independent,similar} [{independent,similar} ...]
                        type of model across studies. 
                                 options: independent, similar (default: similar). can run both.
  --R_var {independent,similar} [{independent,similar} ...]
                        type(s) of model across variants. 
                                 options: independent, similar (default: independent). can run both.
  --M {variant,gene} [{variant,gene} ...]
                        unit(s) of aggregation. 
                                 options: variant, gene (default: gene). can run both.
  --sigma_m_types {sigma_m_mpc_pli,sigma_m_var,sigma_m_1,sigma_m_005} [{sigma_m_mpc_pli,sigma_m_var,sigma_m_1,sigma_m_005} ...]
                        scaling factor(s) for variants.
                                 options: var (i.e. 0.2 for ptvs, 0.05 for pavs/pcvs), 
                                 1, 0.05 (default: var). can run multiple.
  --variants {pcv,pav,ptv} [{pcv,pav,ptv} ...]
                        variant set(s) to consider. 
                                 options: proximal coding [pcv], 
                                          protein-altering [pav], 
                                          protein truncating [ptv] 
                                          (default: ptv). can run multiple.
  --maf_thresh MAF_THRESHES [MAF_THRESHES ...]
                        which MAF threshold(s) to use. must be valid floats between 0 and 1 
                                 (default: 0.01).
  --se_thresh SE_THRESHES [SE_THRESHES ...]
                        which SE threshold(s) to use. must be valid floats between 0 and 1 
                                 (default: 0.2).
  --prior_odds PRIOR_ODDS_LIST [PRIOR_ODDS_LIST ...]
                        which prior odds (can be multiple) to use in calculating posterior 
                                 probabilities. must be valid floats between 0 and 1 (default: 0.0005, expect 
                                 1 in 2000 genes to be a discovery).
  --p_value {farebrother,davies,imhof} [{farebrother,davies,imhof} ...]
                        which method(s) to use to convert Bayes Factors to p-values. if command 
                                 line argument is invoked but method is not specified, will throw an error 
                                 (i.e., specify a method when it is invoked). if not invoked, p-values will not 
                                 be calculated. options: farebrother, davies, imhof. NOTE: --p_value imports R 
                                 objects and methods, which slows down MRP. farebrother is fastest and 
                                 recommended if p-values are a must.
  --exclude EXCLUDE     path to file containing list of variants to exclude from analysis.
                        
                                 format of file:
                        
                                 1:69081:G:C
                                 1:70001:G:A
                                
  --filter_ld_indep     whether or not only ld-independent variants should be kept (default: False;
                                 i.e., use everything).
  --out_folder OUT_FOLDER
                        folder to which output(s) will be written (default: current folder).
                                 if folder does not exist, it will be created.
  --out_filename OUT_FILENAME
                        file prefix with which output(s) will be written (default: underscore-delimited
                                 phenotypes).
```

## Variant groupings

The following groups are how we assign priors (`sigma_m`) to variants within the script. All others are filtered out:

`ptv = ['frameshift_variant', 'splice_acceptor_variant', 'splice_donor_variant', 'stop_gained', 'start_lost', 'stop_lost']`

`pav = ['protein_altering_variant', 'inframe_deletion', 'inframe_insertion', 'splice_region_variant', 'start_retained_variant', 'stop_retained_variant', 'missense_variant']`

`proximal_coding = ['synonymous_variant', '5_prime_UTR_variant', '3_prime_UTR_variant', 'coding_sequence_variant', 'incomplete_terminal_codon_variant', 'TF_binding_site_variant']`
