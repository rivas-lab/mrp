# Multiple Rare-variants and Phenotypes

This directory contains code and documentation for the [Multiple Rare-variants and Phenotypes method](https://www.biorxiv.org/content/10.1101/257162v5) by Venkataraman *et. al.*. The repository is maintained by Guhan Ram Venkataraman (GitHub: guhanrv).

## Script details and options

A full list of options can be obtained by running `python mrp_production.py -h`, and the output is replicated here for reference:

```{bash}
(base) user$ python mrp_production.py -h
usage: mrp_production.py [-h] --file MAP_FILE --metadata_path METADATA_PATH
                         --build {hg19,hg38} [--mean MEAN]
                         [--R_study {independent,similar} [{independent,similar} ...]]
                         [--R_var {independent,similar} [{independent,similar} ...]]
                         [--M {variant,gene} [{variant,gene} ...]]
                         [--sigma_m_types {sigma_m_mpc_pli,sigma_m_var,sigma_m_1,sigma_m_005} [{sigma_m_mpc_pli,sigma_m_var,sigma_m_1,sigma_m_005} ...]]
                         [--variants {pcv,pav,ptv,all} [{pcv,pav,ptv,all} ...]]
                         [--maf_thresh MAF_THRESHES [MAF_THRESHES ...]]
                         [--se_thresh SE_THRESHES [SE_THRESHES ...]]
                         [--prior_odds PRIOR_ODDS_LIST [PRIOR_ODDS_LIST ...]]
                         [--p_value {farebrother,davies,imhof} [{farebrother,davies,imhof} ...]]
                         [--exclude EXCLUDE] [--filter_ld_indep]
                         [--out_folder OUT_FOLDER]
                         [--out_filename OUT_FILENAME]

MRP takes in several variables that affect how it runs.

arguments:
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
                                
  --build {hg19,hg38}   genome build (hg19 or hg3. Required.
  --mean MEAN           prior mean of genetic effects (Default: 0).
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
                                 1, 0.05 (default: mpc_pli). can run multiple.
  --variants {pcv,pav,ptv,all} [{pcv,pav,ptv,all} ...]
                        variant set(s) to consider. 
                                 options: proximal coding [pcv], 
                                          protein-altering [pav], 
                                          protein truncating [ptv],
                                          all variants [all]
                                          (default: ptv). can run multiple.
  --maf_thresh MAF_THRESHES [MAF_THRESHES ...]
                        which MAF threshold(s) to use. must be valid floats between 0 and 1 
                                 (default: 0.01).
  --se_thresh SE_THRESHES [SE_THRESHES ...]
                        which SE threshold(s) to use. must be valid floats between 0 and 1 
                                 (default: 0.2). NOTE: This strict default threshold is best suited for binary
                                 summary statistics. For quantitative traits, we suggest the use of a higher
                                 threshold.
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

The following groups are how we assign priors (`sigma_m`) to variants: Protein-truncating variants (PTVs), Protein-altering variants (PAVs), proximal coding variants (PCVs), and intronic variants ("all" setting above).

`ptv = ['frameshift_variant', 'splice_acceptor_variant', 'splice_donor_variant', 'stop_gained', 'start_lost', 'stop_lost']`. By default, PTVs are assigned a spread (sigma) of 0.2.

`pav = ['protein_altering_variant', 'inframe_deletion', 'inframe_insertion', 'splice_region_variant', 'start_retained_variant', 'stop_retained_variant', 'missense_variant']`. By default, PAVs are assigned a spread (sigma) of 0.05.

`proximal_coding = ['synonymous_variant', '5_prime_UTR_variant', '3_prime_UTR_variant', 'coding_sequence_variant', 'incomplete_terminal_codon_variant', 'TF_binding_site_variant']`. By default, PCVs are assigned a spread (sigma) of 0.03.

`intron = ['regulatory_region_variant', 'intron_variant', 'intergenic_variant', 'downstream_gene_variant', 'mature_miRNA_variant', 'non_coding_transcript_exon_variant', 'upstream_gene_variant', 'NA', 'NMD_transcript_variant']`. By default, intronic variants are assigned a spread (sigma) of 0.02.

These groupings and their sigma values can be changed in the `set_sigmas` method within [`mrp.py`](https://github.com/rivas-lab/mrp/blob/master/mrp.py).

**IMPORTANT NOTE:** If `pav` is selected as the analysis type, then PAVs **and** PTVs are included in the analysis (cascading down). If `pcv` is selected, then PCVs, PAVs **and** PTVs are all included.

## Downloading variant metadata files

We provide variant metadata files for both UK Biobank [array](https://biobankengine.stanford.edu/static/ukb_cal-consequence_wb_maf_gene_ld_indep_mpc_pli.tsv.gz) and [exome](https://biobankengine.stanford.edu/static/ukb_exm_oqfe-consequence_wb_maf_gene_ld_indep_mpc_pli.tsv.gz) for direct download. We generated these files as described in [Venkataraman et. al.](https://www.biorxiv.org/content/10.1101/257162v5).

## Example use cases

We provide for download summary statistics for LDL cholesterol and triglycerides for both array and exome for two populations - a white British cohort as well as a non-British white cohort:

White British:
|       Trait     |     Array     |     Exome    |
| --------------  | ------------- | ------------ |
| LDL Cholesterol | https://biobankengine.stanford.edu/static/wb_ldl_array.glm.linear.gz  | https://biobankengine.stanford.edu/static/wb_ldl_exome.glm.linear.gz |
| Triglycerides  | https://biobankengine.stanford.edu/static/wb_tg_array.glm.linear.gz | https://biobankengine.stanford.edu/static/wb_tg_exome.glm.linear.gz |

non-British white:
|       Trait     |     Array     |     Exome    |
| --------------  | ------------- | ------------ |
| LDL Cholesterol | https://biobankengine.stanford.edu/static/nbw_ldl_array.glm.linear.gz  | https://biobankengine.stanford.edu/static/nbw_ldl_exome.glm.linear.gz |
| Triglycerides  | https://biobankengine.stanford.edu/static/nbw_tg_array.glm.linear.gz | https://biobankengine.stanford.edu/static/nbw_tg_exome.glm.linear.gz |

### Single-trait, single-population gene-based analysis

Say we want to perform a gene-based analysis on the array data for LDL cholesterol amongst both PAVs and PTVs, and also PTVs only. We can do so by creating a "map file" (to be input into `--file`) that looks like the following:

```
path	study	pheno	R_phen
/path/to/wb_ldl_array.glm.linear.gz	wb	ldl	TRUE
```

Then, from the command line, we run:

`python3 mrp.py --file /path/to/map_file --build hg19 --metadata /path/to/ukb_cal-consequence_wb_maf_gene_ld_indep_mpc_pli.tsv.gz --variants pav ptv --se_thresh 100`

Note the use of a non-default higher SE threshold for a quantitative trait. The defaults should take care of the rest.

If we wanted to do the same for the exome data, we would create a map file like:

```
path    study   pheno   R_phen
/path/to/wb_ldl_exome.glm.linear.gz     wb      ldl     TRUE
```

Then run:

`python3 mrp.py --file /path/to/map_file --build hg38 --metadata /path/to/ukb_exm_oqfe-consequence_wb_maf_gene_ld_indep_mpc_pli.tsv.gz --variants pav ptv --se_thresh 100 --filter_ld_indep`

The substantive differences here are the different build, metadata file, and the `--filter_ld_indep` flag, which is suggested for exome data.

### Single-trait gene-based meta-analysis

Let's say that we want to meta-analyze white British and non-British white cohorts together. Functionally, from the command line, this looks no different, but the map files would include an extra line. For example, for array data:

```
path    study   pheno   R_phen
/path/to/wb_ldl_array.glm.linear.gz     wb      ldl     TRUE
/path/to/nbw_ldl_array.glm.linear.gz     nbw      ldl     TRUE
```

MRP takes care of the rest. The same would apply for exome data, with the caveats as in the single-trait gene-based analysis in one population.

### Multi-trait gene-based analysis

Finally, MRP can also handle multi-trait gene-based analysis. Again, the analysis looks no different, except for changes in the map file:

```
path    study   pheno   R_phen
/path/to/wb_ldl_array.glm.linear.gz     wb      ldl     TRUE
/path/to/wb_tg_array.glm.linear.gz     tg      ldl     TRUE
```

### Other optionalities

As mentioned in the `-h` command, MRP can do many things, like incorporate a prior genetic mean of effects, do variant-based analysis (as opposed to gene-based), use independent- or similar-effects assumptions across studies and variants in a block, use different variant scaling factors, exclude variants, and even generate p-values, though this last functionality is currently slow.
