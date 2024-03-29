#!/usr/bin/env python3

from __future__ import division
import argparse, os, itertools, collections, gc, time
from functools import partial, reduce


import pandas as pd
import numpy as np
import numpy.matlib
import scipy.stats
from colorama import Fore, Back, Style


pd.options.mode.chained_assignment = None


def is_pos_def_and_full_rank(X, tol=0.99):

    """
    Ensures a matrix is positive definite and full rank.

    Keep diagonals and multiples every other cell by .99.

    Parameters:
    X: Matrix to verify.
    tol: A tolerance factor for continual multiplication until the matrix is
        singular (Default: 0.99).

    Returns:
    X: Verified (and, if applicable, adjusted) matrix.
    converged: bool for whether or not the matrix is singular.

    """
    X = np.matrix(X)
    if np.all(np.linalg.eigvals(X) > 0):
        return X, True
    else:
        i = 0
        while not np.all(np.linalg.eigvals(X) > 0):
            X = np.diag(np.diag(X)) + tol * X - tol * np.diag(np.diag(X))
            i += 1
            if i > 4:
                return X, False
        return X, True


def safe_inv(X, matrix_name, block, agg_type):

    """
    Safely inverts a matrix, or returns NaN.

    Parameters:
    X: Matrix to invert.
    matrix_name: One of "U"/"v_beta" - used to print messages when inversion fails.
    block: Name of the aggregation block (gene/variant).
        Used to print messages when inversion fails.
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
        Used to print messages when inversion fails.

    Returns:
    X_inv: Inverse of X.

    """

    try:
        X_inv = np.linalg.inv(X)
    except np.linalg.LinAlgError:
        X = is_pos_def_and_full_rank(X)
        try:
            X_inv = np.linalg.inv(X)
        except np.linalg.LinAlgError:
            print("Could not invert " + matrix_name + " for " + agg_type + " " + block+ ".")
            return np.nan
    return X_inv


def farebrother(quad_T, d, fb):

    """
    Farebrother method from CompQuadForm.

    Parameters:

    quad_T: Value point at which distribution function is to be evaluated.
    d: Distinct non-zero characteristic root(s) of A*Sigma.
    fb: Farebrother R method (rpy2 object).

    Returns:
    p_value: Farebrother p-value.

    """

    res = fb(quad_T, d)
    return np.asarray(res)[0]


def davies(quad_T, d, dm):

    """
    Davies method from CompQuadForm.

    Parameters:

    quad_T: Value point at which distribution function is to be evaluated.
    d: Distinct non-zero characteristic root(s) of A*Sigma.
    dm: Davies R method (rpy2 object).

    Returns:
    p_value: Davies p-value.

    """

    res = dm(quad_T, d)
    return np.asarray(res)[0]


def imhof(quad_T, d, im):

    """
    Imhof method from CompQuadForm.

    Parameters:

    quad_T: Value point at which distribution function is to be evaluated.
    d: Distinct non-zero characteristic root(s) of A*Sigma.
    im: Imhof R method (rpy2 object).

    Returns:
    p_value: Imhof p-value.

    """

    res = im(quad_T, d)
    return np.asarray(res)[0]


def initialize_r_objects():

    """
    Initializes Farebrother, Davies, and Imhof R methods as rpy2 objects.

    Returns:
    fb: Farebrother R method (rpy2 object).
    dm: Davies R method (rpy2 object).
    im: Imhof R method (rpy2 object).

    """

    robjects.r(
    """
    require(MASS)
    require(CompQuadForm)
    farebrother.method <- function(quadT, d, h = rep(1, length(d)), delta = rep(0, length(d)), maxiter = 100000, epsilon = 10^-16, type = 1) {
        return(farebrother(quadT, d, h, delta, maxit = as.numeric(maxiter), eps = as.numeric(epsilon), mode = as.numeric(type))$Qq)
    }
    """)
    robjects.r(
    """
    require(MASS)
    require(CompQuadForm)
    imhof.method <- function(quadT, d, h = rep(1, length(d)), delta = rep(0, length(d)), epsilon = 10^-16, lim = 10000) {
        return(imhof(quadT, d, h, delta, epsabs = as.numeric(epsilon), epsrel = as.numeric(epsilon), limit=as.numeric(lim))$Qq)
    }
    """)
    robjects.r(
    """
    require(MASS)
    require(CompQuadForm)
    davies.method <- function(quadT, d, h = rep(1, length(d)), delta = rep(0, length(d)), sig = 0, limit = 10000, accuracy = 0.0001) {
        return(davies(quadT, d, h, delta, sigma=as.numeric(sig), lim = as.numeric(limit), acc = as.numeric(accuracy))$Qq)
    }
    """)
    fb = robjects.globalenv["farebrother.method"]
    fb = robjects.r["farebrother.method"]
    im = robjects.globalenv["imhof.method"]
    im = robjects.r["imhof.method"]
    dm = robjects.globalenv["davies.method"]
    dm = robjects.r["davies.method"]
    return fb, dm, im


def return_BF_pvals(beta, U, v_beta, v_beta_inv, fb, dm, im, methods):

    """
    Computes a p-value from the quadratic form that is subsumed by the Bayes Factor.

    Parameters:

    beta: Effect size vector without missing data.
    U: Kronecker product of the three matrices (S*M*K x S*M*K)
        dictating correlation structures; no missing data.
    v_beta: Diagonal matrix of variances of effect sizes without missing data.
    v_beta_inv: Inverse of v_beta.
    fb: Farebrother R method (rpy2 object).
    dm: Davies R method (rpy2 object).
    im: Imhof R method (rpy2 object).
    methods: List of p-value generating method(s) to apply to our data.

    Returns:
    p_values: List of p-values corresponding to each method specified as input.

    """

    n = beta.shape[0]
    A = v_beta + U
    A, _ = is_pos_def_and_full_rank(A)
    if np.any(np.isnan(A)):
        return [np.nan] * len(methods)
    A_inv = np.linalg.inv(A)
    quad_T = np.asmatrix(beta.T) * np.asmatrix((v_beta_inv - A_inv)) * np.asmatrix(beta)
    B, _ = is_pos_def_and_full_rank(
        np.matlib.eye(n) - np.asmatrix(A_inv) * np.asmatrix(v_beta)
    )
    if np.any(np.isnan(B)):
        return [np.nan] * len(methods)
    d = np.linalg.eig(B)[0]
    d = [i for i in d if i > 0.01]
    p_values = collections.deque([])
    for method in methods:
        if method == "farebrother":
            p_value = farebrother(quad_T, d, fb)
        elif method == "davies":
            p_value = davies(quad_T, d, dm)
        elif method == "imhof":
            p_value = imhof(quad_T, d, im)
        p_value = max(0, min(1, p_value))
        p_values.append(p_value)
    return p_values


def compute_posterior_probs(log10BF, prior_odds_list):

    """
    Computes posterior probability given prior odds and a log10 Bayes Factor.

    Parameters:
    log10BF: log10 Bayes Factor of given association.
    prior_odds_list: List of assumed prior odds.

    Returns:
    posterior_probs: List of posterior probabilities of the event
        given the list of prior odds and the Bayes Factor.

    """

    BF = 10 ** (log10BF)
    posterior_odds_list = [prior_odds * BF for prior_odds in prior_odds_list]
    posterior_probs = [
        (posterior_odds / (1 + posterior_odds))
        for posterior_odds in posterior_odds_list
    ]
    return posterior_probs


def return_BF(
    U, beta, v_beta, mu, block, agg_type, prior_odds_list, p_value_methods, fb, dm, im
):

    """
    Given quantities calculated previously and the inputs, returns the associated
        Bayes Factor.

    Parameters:
    U: Kronecker product of the three matrices (S*M*K x S*M*K)
        dictating correlation structures; no missing data.
    beta: Effect size vector without missing data.
    v_beta: Diagonal matrix of variances of effect sizes without missing data.
    mu: A mean of genetic effects, size of beta
        (NOTE: default is 0, can change in the code below).
    block: Name of the aggregation block (gene/variant).
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
    prior_odds_list: List of prior odds used as assumptions to calculate
        posterior probabilities of Bayes Factors.
    p_value_methods: List of p-value methods used to calculate p-values from
        Bayes Factors.
    fb, dm, im: initialized R functions for Farebrother, Davies, and Imhof methods.
        NoneType if p_value_methods is [].

    Returns:, []
    log10BF: log_10 Bayes Factor (ratio of marginal likelihoods of alternative model,
        which accounts for priors, and null).
    posterior_probs: List of posterior probabilities corresponding to each prior odds
         in prior_odds_list.
    p_values: List of p-values corresponding to each method in p_value_methods.
    converged: whether or not v_beta_inv and U_inv are defined.

    """
    v_beta_inv = safe_inv(v_beta, "v_beta", block, agg_type)
    U_inv = safe_inv(U, "U", block, agg_type)
    if v_beta_inv is not np.nan and U_inv is not np.nan:
        sum_inv = safe_inv(U_inv + v_beta_inv, "U_inv + v_beta_inv", block, agg_type)
        if sum_inv is np.nan:
            np.nan, [], [], False
        fat_middle = v_beta_inv - (v_beta_inv.dot(sum_inv)).dot(v_beta_inv)
        logBF = (
            -0.5 * np.linalg.slogdet(np.matlib.eye(beta.shape[0]) + v_beta_inv * U)[1]
            + 0.5 * beta.T.dot(v_beta_inv.dot(beta))
            - 0.5 * (((beta - mu).T).dot(fat_middle)).dot(beta - mu)
        )
        logBF = float(np.array(logBF))
        log10BF = logBF / np.log(10)
        posterior_probs = (
            compute_posterior_probs(log10BF, prior_odds_list) if prior_odds_list else []
        )
        p_values = (
            return_BF_pvals(beta, U, v_beta, v_beta_inv, fb, dm, im, p_value_methods)
            if p_value_methods
            else []
        )
        return log10BF, posterior_probs, p_values, True
    else:
        return np.nan, [], [], False


def delete_rows_and_columns(X, indices_to_remove):

    """
    Helper function to delete rows and columns from a matrix.

    Parameters:
    X: Matrix that needs adjustment.
    indices_to_remove: Rows and columns to be deleted.

    Returns:
    X: Smaller matrix that has no missing data.

    """

    X = np.delete(X, indices_to_remove, axis=0)
    X = np.delete(X, indices_to_remove, axis=1)
    return X


def adjust_for_missingness(U, omega, beta, se, beta_list):

    """
    Deletes rows and columns where we do not have effect sizes/standard errors.

    Calls method delete_rows_and_columns, a helper function that calls the numpy
        command.

    Parameters:
    U: Kronecker product of the three matrices (S*M*K x S*M*K)
        dictating correlation structures; may relate to missing data.
    omega: (S*M*K x S*M*K) matrix that contains correlation of errors
        across variants, studies, and phenotypes.
    beta: Vector of effect sizes within the unit of aggregation;
        may contain missing data.
    se: Vector of standard errors within the unit of aggregation;
        may contain missing data.
    beta_list: List of effect sizes within the unit of aggregation;
        may contain missing data.

    Returns:
    U: Potentially smaller U matrix not associated with missing data.
    omega: Potentially smaller omega matrix not associated with missing data.
    beta: Potentially smaller beta vector without missing data.
    se: Potentially smaller SE vector without missing data.

    """

    indices_to_remove = np.argwhere(np.isnan(beta_list))
    U = delete_rows_and_columns(U, indices_to_remove)
    omega = delete_rows_and_columns(omega, indices_to_remove)
    beta = beta[~np.isnan(beta)].reshape(-1, 1)
    se = se[~np.isnan(se)]
    return U, omega, beta, se


def generate_beta_se(subset_df, pops, phenos):

    """
    Gathers effect sizes and standard errors from a unit of aggregation (gene/variant).

    Parameters:
    subset_df: Slice of the original dataframe that encompasses the current unit of
        aggregation (gene/variant).
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.

    Returns:
    beta_list: A list of effect sizes (some may be missing) from the subset.
    se_list: A list of standard errors (some may be missing) from the subset.

    """

    beta_list = collections.deque([])
    se_list = collections.deque([])
    for pop in pops:
        for pheno in phenos:
            if ("BETA_" + pop + "_" + pheno) in subset_df.columns:
                beta_list.extend(list(subset_df["BETA_" + pop + "_" + pheno]))
                se_list.extend(list(subset_df["SE_" + pop + "_" + pheno]))
            else:
                beta_list.extend([np.nan] * len(subset_df))
                se_list.extend([np.nan] * len(subset_df))
    return beta_list, se_list


def calculate_all_params(
    df,
    pops,
    phenos,
    key,
    sigma_m_type,
    R_study,
    R_phen,
    R_var_model,
    agg_type,
    M,
    err_corr,
    mean,
):

    """
    Calculates quantities needed for MRP (U, beta, v_beta, mu).

    Parameters:
    df: Merged, filtered, and annotated dataframe containing summary statistics.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    key: Variant/gene name.
    sigma_m_type: One of "sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005".
        Dictates variant scaling factor by functional annotation.
    R_study: R_study matrix to use for analysis (independent/similar).
    R_phen: R_phen matrix to use for analysis (empirically calculated).
    R_var_model: String ("independent"/"similar") corresponding to R_var matrices to
        use for analysis.
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
    M: Number of variants within the gene block if agg_type is "gene"; if "variant", 1.
    err_corr: A (S*K x S*K) matrix of correlation of errors across studies
        and phenotypes. Used to calculate v_beta.
    mean: Prior mean of genetic effects to use (from command line).

    Returns:
    U: Kronecker product of the three matrices (S*M*K x S*M*K)
        dictating correlation structures, adjusted for missingness.
    beta: A S*M*K x 1 vector of effect sizes.
    v_beta: A (S*M*K x S*M*K) matrix of variances of effect sizes.
    mu: A mean of genetic effects, size of beta
        (NOTE: default is 0, can change in the code below).
    converged: whether or not U is pos-def/full-rank.
    num_variants_mpc: the nummber of MPC-augmented variants in the gene.
    num_variants_pli: the number of pLI-augmented variants in the gene.

    """
    subset_filter_col = "gene_symbol" if agg_type == "gene" else "V"
    subset_df = df.loc[np.in1d(df[subset_filter_col], [key]), ]
    if sigma_m_type == "sigma_m_mpc_pli":
        num_variants_pli = np.sum(np.logical_and(
            np.in1d(subset_df['category'], ['ptv']),
            np.in1d(subset_df['pLI'], ['True'])
        ))
        num_variants_mpc = np.sum(np.logical_and(
            np.in1d(subset_df['category'], ['pav']),
            (subset_df['MPC'] >= 1)
        ))
    else:
        num_variants_mpc, num_variants_pli = None, None
    sigma_m = np.array(subset_df[sigma_m_type])
    diag_sigma_m = np.diag(np.atleast_1d(sigma_m))
    R_var = np.diag(np.ones(M)) if R_var_model == "independent" else np.ones((M, M))
    R_var, _ = is_pos_def_and_full_rank(R_var)
    R_study, _ = is_pos_def_and_full_rank(R_study)
    R_phen, _ = is_pos_def_and_full_rank(R_phen)
    S_var = np.dot(np.dot(diag_sigma_m, R_var), diag_sigma_m)
    beta_list, se_list = generate_beta_se(subset_df, pops, phenos)
    beta = np.array(beta_list).reshape(-1, 1)
    se = np.array(se_list)
    omega = np.kron(err_corr, np.diag(np.ones(M)))
    U = np.kron(np.kron(R_study, R_phen), S_var)
    U, omega, beta, se = adjust_for_missingness(U, omega, beta, se, beta_list)
    U, converged = is_pos_def_and_full_rank(U, 0.8)
    diag_se = np.diag(se)
    v_beta = np.dot(np.dot(diag_se, omega), diag_se)
    v_beta, _ = is_pos_def_and_full_rank(v_beta)
    mu = np.ones(beta.shape) * mean
    return U, beta, v_beta, mu, converged, num_variants_mpc, num_variants_pli


def output_file(
    bf_dfs, agg_type, pops, phenos, maf_thresh, se_thresh, out_folder, out_filename, chrom
):

    """
    Outputs a file containing aggregation unit and Bayes Factors.

    Parameters:
    bf_dfs: List of dataframes containing Bayes Factors from each analysis.
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    maf_thresh: Maximum MAF of variants in this run.
    se_thresh: Upper threshold for SE for this run.
    out_folder: Output folder in which results are stored.
    out_filename: Optional prefix for file output.
    chrom: List of chromosomes (optional) from command line.

    """
    outer_merge = partial(pd.merge, on=[agg_type], how="outer")
    out_df = reduce(outer_merge, bf_dfs)
    if not os.path.exists(out_folder):
        os.makedirs(out_folder)
        print("")
        print(Fore.RED + "Folder " + out_folder + " created." + Style.RESET_ALL)
        print("")
    if not out_filename:
        out_file = os.path.join(out_folder, "_".join(pops) + "_" + "_".join(phenos) + "_" + agg_type + "_maf_" + str(maf_thresh) + "_se_" + str(se_thresh) + "_chrs_" + "_".join(chrom) + ".tsv.gz")
    else:
        out_file = os.path.join(out_folder, "_".join(pops) + "_" + out_filename + "_" + agg_type + "_maf_" + str(maf_thresh) + "_se_" + str(se_thresh) + ".tsv.gz")
    sort_col = [col for col in out_df.columns if "log_10_BF" in col][0]
    out_df = out_df.sort_values(by=sort_col, ascending=False)
    out_df.to_csv(out_file, sep="\t", index=False, compression="gzip")
    print("")
    print(Fore.RED + "Results written to " + out_file + "." + Style.RESET_ALL)
    print("")


def get_output_file_columns(
    agg_type,
    R_study_model,
    R_var_model,
    sigma_m_type,
    analysis,
    prior_odds_list,
    p_value_methods,
):

    """
    Sets up the columns that must be enumerated in the output dataframe from MRP.

    Parameters:
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
    R_study_model: String ("independent"/"similar") corresponding to R_study.
    R_var_model: String ("independent"/"similar") corresponding to R_var matrices to
        use for analysis.
    sigma_m_type: One of "sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005".
        scaling factor by functional annotation.
    analysis: One of "ptv"/"pav"/"pcv". Dictates which variants are included.
    prior_odds_list: List of prior odds used as assumptions to calculate posterior
        probabilities of Bayes Factors.
    p_value_methods: List of p-value methods used to calculate p-values from Bayes
        Factors.

    Returns:
    bf_df_columns: Columns needed for the output file.
    fb: Farebrother R method (rpy2 object), or None if --p_value is not invoked.
    dm: Davies R method (rpy2 object), or None if --p_value is not invoked.
    im: Imhof R method (rpy2 object), or None if --p_value is not invoked.

    """

    bf_df_columns = collections.deque([agg_type])
    if agg_type == "gene":
        bf_df_columns.extend(["num_variants_" + analysis])
        if sigma_m_type == "sigma_m_mpc_pli":
            bf_df_columns.extend(
                ["num_variants_mpc_" + analysis, "num_variants_pli_" + analysis]
            )
    bf_df_columns.extend(
        [
            "log_10_BF"
            + "_study_"
            + R_study_model
            + "_var_"
            + R_var_model
            + "_"
            + sigma_m_type
            + "_"
            + analysis
        ]
    )
    if prior_odds_list:
        bf_df_columns.extend(
            [
                "posterior_prob_w_prior_odds_"
                + str(prior_odds)
                + "_study_"
                + R_study_model
                + "_var_"
                + R_var_model
                + "_"
                + sigma_m_type
                + "_"
                + analysis
                for prior_odds in prior_odds_list
            ]
        )
    if p_value_methods:
        fb, dm, im = initialize_r_objects()
        bf_df_columns.extend(
            [
                "p_value_"
                + p_value_method
                + "_study_"
                + R_study_model
                + "_var_"
                + R_var_model
                + "_"
                + sigma_m_type
                + "_"
                + analysis
                for p_value_method in p_value_methods
            ]
        )
    else:
        fb = dm = im = None
    return bf_df_columns, fb, dm, im


def run_mrp(
    df,
    S,
    K,
    pops,
    phenos,
    R_study,
    R_study_model,
    R_phen,
    err_corr,
    R_var_model,
    analysis,
    sigma_m_type,
    agg_type,
    prior_odds_list,
    p_value_methods,
    mean,
):

    """
    Runs MRP with the given parameters.

    Parameters:
    df: Merged dataframe containing all relevant summary statistics.
    S: Number of populations/studies.
    K: Number of phenotypes.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    R_study: R_study matrix to use for analysis (independent/similar).
    R_study_model: String ("independent"/"similar") corresponding to R_study.
    R_phen: R_phen matrix to use for analysis (empirically calculated).
    err_corr: A (S*K x S*K) matrix of correlation of errors across studies and
        phenotypes. Used to calculate v_beta.
    R_var_model: String ("independent"/"similar") corresponding to R_var matrices to
        use for analysis.
    analysis: One of "ptv"/"pav"/"pcv". Dictates which variants are included.
    sigma_m_type: One of "sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005".
        scaling factor by functional annotation.
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
    prior_odds_list: List of prior odds used as assumptions to calculate posterior
        probabilities of Bayes Factors.
    p_value_methods: List of p-value methods used to calculate p-values from Bayes
        Factors.
    mean: Prior mean of genetic effects to use (from command line).

    Returns:
    bf_df: Dataframe with log_10 Bayes Factor, posterior odds, and p-value (if applicable).

    """
    m_dict = (
        df.groupby("gene_symbol").size()
        if agg_type == "gene"
        else df.groupby("V").size()
    )
    bf_df_columns, fb, dm, im = get_output_file_columns(
        agg_type,
        R_study_model,
        R_var_model,
        sigma_m_type,
        analysis,
        prior_odds_list,
        p_value_methods,
    )
    data = collections.deque([])
    num_converged = 0
    for i, (key, value) in enumerate(m_dict.items()):
        if i % 1000 == 0:
            print("Done " + str(i) + " " + agg_type + "s out of " + str(len(m_dict)))
            gc.collect()
        M = value
        U, beta, v_beta, mu, converged, num_variants_mpc, num_variants_pli = calculate_all_params(
            df,
            pops,
            phenos,
            key,
            sigma_m_type,
            R_study,
            R_phen,
            R_var_model,
            agg_type,
            M,
            err_corr,
            mean,
        )
        bf, posterior_probs, p_values, converged = return_BF(
            U,
            beta,
            v_beta,
            mu,
            key,
            agg_type,
            prior_odds_list,
            p_value_methods,
            fb,
            dm,
            im,
        )
        if converged:
            num_converged += 1
        if agg_type == "gene" and sigma_m_type != "sigma_m_mpc_pli":
            data.append([key, beta.shape[0], bf] + posterior_probs + p_values)
        elif agg_type == "gene" and sigma_m_type == "sigma_m_mpc_pli":
            data.append(
                [key, beta.shape[0], num_variants_mpc, num_variants_pli, bf]
                + posterior_probs
                + p_values
            )
        else:
            data.append([key, bf] + posterior_probs + p_values)
    print("")
    print(
        str(num_converged)
        + "/"
        + str(len(m_dict))
        + " genes' matrices had well-behaved eigenvalues."
    )
    bf_df = pd.DataFrame(data, columns=bf_df_columns)
    return bf_df


def print_params(
    analysis,
    R_study_model,
    R_var_model,
    agg_type,
    sigma_m_type,
    maf_thresh,
    se_thresh,
    prior_odds_list,
    p_value_methods,
    mean,
):

    """
    Provides a text overview of each analysis in the terminal.

    Parameters:
    analysis: One of "ptv"/"pav"/"pcv". Dictates which variants are included.
    R_study_model: One of "independent"/"similar". Dictates correlation structure
        across studies.
    R_var_model: One of "independent"/"similar". Dictates correlation structure
        across variants.
    agg_type: One of "gene"/"variant". Dictates block of aggregation.
    sigma_m_type: One of "sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005".
        scaling factor by functional annotation.
    maf_thresh: Maximum MAF of variants in this run.
    prior_odds_list: List of prior odds used as assumptions to calculate posterior
        probabilities of Bayes Factors.
    p_value_methods: List of p-value methods used to calculate p-values from Bayes
        Factors.

    """

    print("")
    print(Fore.YELLOW + "Analysis: " + Style.RESET_ALL + analysis)
    print(Fore.YELLOW + "R_study model: " + Style.RESET_ALL + R_study_model)
    print(Fore.YELLOW + "R_var model: " + Style.RESET_ALL + R_var_model)
    print(Fore.YELLOW + "Aggregation by: " + Style.RESET_ALL + agg_type)
    print(Fore.YELLOW + "Variant weighting factor: " + Style.RESET_ALL + sigma_m_type)
    print(Fore.YELLOW + "MAF threshold: " + Style.RESET_ALL + str(maf_thresh))
    print(Fore.YELLOW + "SE threshold: " + Style.RESET_ALL + str(se_thresh))
    print(Fore.YELLOW + "Prior mean: " + Style.RESET_ALL + str(mean))
    if prior_odds_list:
        print(Fore.YELLOW + "Prior odds: " + Style.RESET_ALL + ", ".join([str(prior_odd) for prior_odd in prior_odds_list]))
    if p_value_methods:
        print(Fore.YELLOW + "Methods for p-value generation: " + Style.RESET_ALL + ", ".join(p_value_methods))
    print("")


def filter_category(df, variant_filter):

    """
    Filters a set of dataframes that have been read in based on functional consequence.

    Dependent on the variant filter that is dictated by the analysis.

    Parameters:
    df: Merged dataframe containing all summary statistics.
    variant_filter: The variant filter dictated by the analysis ("ptv"/"pav"/"pcv").

    Returns:
    df: Merged dataframe containing all relevant summary statistics;
        filters out variants excluded from analysis.

    """

    if variant_filter == "ptv":
        df = df[df.category == "ptv"]
    elif variant_filter == "pav":
        df = df[(df.category == "ptv") | (df.category == "pav")]
    elif variant_filter == "pcv":
        df = df[(df.category == "ptv") | (df.category == "pav") | (df.category == "pcv")]
    return df


def loop_through_parameters(
    df,
    se_thresh,
    maf_threshes,
    agg,
    variant_filters,
    S,
    R_study_list,
    R_study_models,
    pops,
    K,
    R_phen,
    phenos,
    R_var_models,
    sigma_m_types,
    err_corr,
    prior_odds_list,
    p_value_methods,
    out_folder,
    out_filename,
    mean,
    chrom,
):

    """
    Loops through parameters specified through command line (or defaults).

    Parameters:
    df: Merged dataframe containing all summary statistics.
    se_thresh: Upper threshold for SE for this run.
    maf_threshes: List of maximum MAFs of variants in your runs.
    agg: Unique list of aggregation units ("gene"/"variant") to use for analysis.
    variant_filters: Unique list of variant filters ("ptv"/"pav"/"pcv","all") to use
        for analysis.
    S: Number of populations/studies.
    R_study_list: Unique list of R_study matrices to use for analysis.
    R_study_models: Unique strings ("independent"/"similar") corresponding to each
        matrix in R_study_list.
    pops: Unique set of populations (studies) to use for analysis.
    K: Number of phenotypes.
    R_phen: R_phen matrix to use for analysis (empirically calculated).
    phenos: Unique set of phenotypes to use for analysis.
    R_var_models: Unique strings ("independent"/"similar") corresponding to R_var
        matrices to use for analysis.
    sigma_m_types: Unique list of sigma_m types ("sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005")
        to use for analysis.
    err_corr: Matrix of correlation of errors across studies and phenotypes.
    prior_odds_list: List of prior odds used as assumptions to calculate posterior
        probabilities of Bayes Factors.
    p_value_methods: List of p-value methods used to calculate p-values from Bayes
        Factors.
    out_folder: Folder where output will be placed.
    out_filename: Optional prefix for file output.
    chrom: List of chromosomes (optional) from command line.

    """

    if (S == 1) and (len(R_study_models) > 1):
        print(Fore.YELLOW + "Since we are not meta-analyzing, R_study is just [1]." + Style.RESET_ALL)
        print("")
        R_study_models = ["similar"]
        R_study_list = [R_study_list[0]]
    for maf_thresh in maf_threshes:
        print(Fore.YELLOW + "Running MRP across parameters for MAF threshold " + str(maf_thresh) + " and SE threshold " + str(se_thresh) + "..." + Style.RESET_ALL)
        maf_df = df[(df.maf <= maf_thresh) & (df.maf >= 0)]
        for agg_type in agg:
            bf_dfs = collections.deque([])
            # If not aggregating, then R_var choice does not affect BF
            if (agg_type == "variant") and (len(R_var_models) > 1):
                print(Fore.YELLOW + "Since we are not aggregating, R_var is just [1]." + Style.RESET_ALL)
                R_var_models = ["independent"]
            for analysis in variant_filters:
                analysis_df = filter_category(maf_df, analysis)
                analysis_bf_dfs = collections.deque([])
                for sigma_m_type in sigma_m_types:
                    sigma_m_type_bf_dfs = collections.deque([])
                    for R_study, R_study_model in zip(R_study_list, R_study_models):
                        for R_var_model in R_var_models:
                            print_params(
                                analysis,
                                R_study_model,
                                R_var_model,
                                agg_type,
                                sigma_m_type,
                                maf_thresh,
                                se_thresh,
                                prior_odds_list,
                                p_value_methods,
                                mean,
                            )
                            bf_df = run_mrp(
                                analysis_df,
                                S,
                                K,
                                pops,
                                phenos,
                                R_study,
                                R_study_model,
                                R_phen,
                                err_corr,
                                R_var_model,
                                analysis,
                                sigma_m_type,
                                agg_type,
                                prior_odds_list,
                                p_value_methods,
                                mean,
                            )
                            sigma_m_type_bf_dfs.append(bf_df)
                    if sigma_m_type == "sigma_m_mpc_pli":
                        outer_merge = partial(
                            pd.merge,
                            on=[
                                agg_type,
                                "num_variants_" + analysis,
                                "num_variants_mpc_" + analysis,
                                "num_variants_pli_" + analysis,
                            ],
                            how="outer",
                        )
                    else:
                        outer_merge = partial(
                            pd.merge,
                            on=[agg_type, "num_variants_" + analysis],
                            how="outer",
                        )
                    sigma_m_type_bf_df = reduce(outer_merge, sigma_m_type_bf_dfs)
                    analysis_bf_dfs.append(sigma_m_type_bf_df)
                if agg_type == "gene":
                    outer_merge = partial(
                        pd.merge, on=[agg_type, "num_variants_" + analysis], how="outer"
                    )
                else:
                    outer_merge = partial(pd.merge, on=[agg_type], how="outer")
                analysis_bf_df = reduce(outer_merge, analysis_bf_dfs)
                bf_dfs.append(analysis_bf_df)
            output_file(
                bf_dfs,
                agg_type,
                pops,
                phenos,
                maf_thresh,
                se_thresh,
                out_folder,
                out_filename,
                chrom,
            )


def get_sigma_and_consequence_categories():
    """
    Here we define two constants: consequence category and sigma_m value for each consequence category
    """
    sigma_m = {
        'ptv':    0.2,
        'pav':    0.05,
        'pcv':    0.03,
        'intron': 0.03,
        'utr':    0.03,
        'others': 0.02,
    }
    consequence_categories = {
        'ptv': [
            "splice_acceptor_variant",
            "splice_donor_variant",
            "stop_lost",
            "stop_gained",
            "frameshift_variant",
            "transcript_ablation",
            "start_lost",
            "pLoF",
        ],
        'pav': [
            "missense_variant",
            "splice_region_variant",
            "protein_altering_variant",
            "inframe_insertion",
            "inframe_deletion",
            "missense",
            "LC",
        ],
        'pcv': [
            "stop_retained_variant",
            "coding_sequence_variant",
            "incomplete_terminal_codon_variant",
            "synonymous_variant",
            "start_retained_variant",
        ],
        'intron': [
            "intron_variant",
        ],
        'utr': [
            "5_prime_UTR_variant",
            "3_prime_UTR_variant",
        ],
        'others': [
            "regulatory_region_variant",
            "non_coding_transcript_variant",
            "mature_miRNA_variant",
            "NMD_transcript_variant",
            "intergenic_variant",
            "upstream_gene_variant",
            "downstream_gene_variant",
            "TF_binding_site_variant",
            "non_coding_transcript_exon_variant",
            "regulatory_region_ablation",
            "TFBS_ablation",
            "NA",
        ]
    }
    return(sigma_m, consequence_categories)


def get_sigma_m_var_df():

    """
    Prepare a pandas dataframe with the following three columns:
    category, most_severe_consequence, sigma_m_var
    """

    sigma_m, consequence_categories = get_sigma_and_consequence_categories()

    return(pd.DataFrame(
        list(itertools.chain(*[
            [(category, csq) for csq in csqs] for category, csqs in consequence_categories.items()
        ])),
        columns=['category', 'most_severe_consequence']
    ).merge(
        pd.DataFrame(
            sigma_m.items(),
            columns=['category', 'sigma_m_var']
        )
    ))


def compute_sigma_m_mpc_pli(sigma_m_var, category, pLI, MPC):

    """
    Computes sigma_m_mpc_pli value
    """
    if(sigma_m_var is None):
        return None
    elif((category == 'ptv') and (pLI == 'True')):
        return(2 * sigma_m_var)
    elif((category == 'pav') and (MPC >= 1)):
        return(MPC * sigma_m_var)
    else:
        return(sigma_m_var)


def set_sigmas(df, sigma_m_types):

    """
    Assigns appropriate sigmas to appropriate variants by annotation.

    Sets sigmas based on user input: functional annotation (var); uniform
        sigma (1 and 0.05), or those incorporating MPC/pLI.

    Parameters:
    df: Merged dataframe containing all variants across all studies and phenotypes.

    Returns:
    df: Merged dataframe with a subset of four additional columns:
        sigma_m_mpc_pli: Column of sigma values (mapped to functional annotation via the
            lists inside this method + adding pLI and MPC effects).
        sigma_m_var: Column of sigma values (mapped to functional annotation via the
            lists inside this method).
            NOTE: One can change the sigmas associated with each type of variant by
                adjusting the values in get_sigma_and_consequence_categories() method.
        sigma_m_1: Constant column of 1.
        sigma_m_005: Constant column of 0.05.

    """

    if "sigma_m_1" in sigma_m_types:
        df = df.assign(sigma_m_1=1)

    if "sigma_m_005" in sigma_m_types:
        df = df.assign(sigma_m_005=0.05)

    if ("sigma_m_var" in sigma_m_types) or ("sigma_m_mpc_pli" in sigma_m_types):
        df = df.merge(get_sigma_m_var_df(), how = 'left', on = 'most_severe_consequence')

    if "sigma_m_mpc_pli" in sigma_m_types:
        df['sigma_m_mpc_pli'] = df.apply(
            lambda x: compute_sigma_m_mpc_pli(x.sigma_m_var, x.category, x.pLI, x.MPC),
            axis=1
        )

    return df


def get_betas(df, pop1, pheno1, pop2, pheno2, mode):

    """
    Retrieves betas from a pair of (pop, pheno) tuples using non-significant,
        non-missing variants.

    Parameters:
    df: Merged dataframe containing summary statistics.
    pop1: First population.
    pheno1: First phenotype.
    pop2: Second population.
    pheno2: Second phenotype.
    mode: One of "null", "sig". Determines whether we want to sample from null or
        significant variants. Useful for building out correlations of errors and
        phenotypes respectively.

    Returns:
    beta1: List of effect sizes from the first (pop, pheno) tuple; used to compute
        correlation.
    beta2: List of effect sizes from the second (pop, pheno) tuple; used to compute
        correlation.

    """

    if ("P_" + pop1 + "_" + pheno1 not in df.columns) or (
        "P_" + pop2 + "_" + pheno2 not in df.columns
    ):
        return [], []
    if mode == "null":
        df = df[
            (df["P_" + pop1 + "_" + pheno1].astype(float) >= 1e-2)
            & (df["P_" + pop2 + "_" + pheno2].astype(float) >= 1e-2)
        ]
    elif mode == "sig":
        df = df[
            (df["P_" + pop1 + "_" + pheno1].astype(float) <= 1e-5)
            | (df["P_" + pop2 + "_" + pheno2].astype(float) <= 1e-5)
        ]
    beta1 = list(df["BETA_" + pop1 + "_" + pheno1])
    beta2 = list(df["BETA_" + pop2 + "_" + pheno2])
    return beta1, beta2


def calculate_phen(a, b, pop1, pheno1, pop2, pheno2, df, pop_pheno_tuples):

    """
    Calculates a single entry in the phen_corr matrix.

    Parameters:
    a, b: Positional parameters within the phen_corr matrix.
    pop1: Name of first population.
    pheno1: Name of first phenotype.
    pop2: Name of second population.
    pheno2: Name of second phenotype.
    df: Dataframe containing significant, common, LD-independent variants.
    pop_pheno_tuples: Indicate which populations/phenotypes to use to build R_phen.

    Returns:
    phen_corr[a, b]: One entry in the phen_corr matrix.
    """
    # If in lower triangle, do not compute; symmetric matrix
    if (a > b) or (a == b):
        return np.nan
    else:
        # if this combination of pop, pheno doesn't exist in the map file, then nan
        if ((pop1, pheno1) in pop_pheno_tuples) and (
            (pop2, pheno2) in pop_pheno_tuples
        ):
            phen_beta1, phen_beta2 = get_betas(df, pop1, pheno1, pop2, pheno2, "sig")
            if phen_beta1 is not None:
                corr, p = scipy.stats.pearsonr(phen_beta1, phen_beta2)
                return corr if (p <= 0.01) else np.nan
            return np.nan
        return np.nan


def build_phen_corr(S, K, pops, phenos, df, pop_pheno_tuples):

    """
    Builds out a matrix of correlations between all phenotypes and studies using:
        - significant (P < 1e-5)
        - common (MAF >= 0.01)
        - LD-independent
    SNPs.

    Parameters:
    S: Number of populations/studies.
    K: Number of phenotypes.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    df: Merged dataframe containing all relevant summary statistics.
    pop_pheno_tuples: Indicate which populations/phenotypes to use to build R_phen.

    Returns:
    phen_corr: (S*K x S*K) matrix of correlations between all phenotypes and studies
        for significant variants. Used to calculate R_phen.

    """
    phen_corr = np.zeros((S * K, S * K))
    for i, pop1 in enumerate(pops):
        for j, pheno1 in enumerate(phenos):
            for x, pop2 in enumerate(pops):
                for y, pheno2 in enumerate(phenos):
                    # Location in matrix
                    a, b = K * i + j, K * x + y
                    phen_corr[a, b] = calculate_phen(
                        a, b, pop1, pheno1, pop2, pheno2, df, pop_pheno_tuples
                    )
    return phen_corr


def filter_for_phen_corr(df, map_file):

    """
    Filters the initial dataframe for the criteria used to build R_phen.

    Parameters:
    df: Merged dataframe containing all summary statistics.
    map_file: Dataframe indicating which summary statistics to use to build R_phen.

    Returns:
    df: Filtered dataframe that contains significant, common, LD-independent variants.
    pop_pheno_tuples: Distinct coupled pop/pheno combinations.

    """

    files_to_use = map_file[map_file["R_phen"] == "True"]
    if len(files_to_use) == 0:
        return [], []
    pop_pheno_tuples = zip(list(files_to_use["study"]), list(files_to_use["pheno"]))
    cols_to_keep = collections.deque(["V", "maf", "ld_indep"])
    for col_type in "BETA_", "P_":
        cols_to_keep.extend(
            [col_type + pop + "_" + pheno for pop, pheno in pop_pheno_tuples]
        )
    df = df[cols_to_keep]
    # Get only LD-independent, common variants
    df = df[(df.maf >= 0.01) & (df.ld_indep == "True")]
    df = df.dropna(axis=1, how="all")
    df = df.dropna()
    return df, pop_pheno_tuples


def build_R_phen(S, K, pops, phenos, df, map_file):

    """
    Builds R_phen using phen_corr (calculated using the method directly above this).

    Parameters:
    S: Number of populations/studies.
    K: Number of phenotypes.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    df: Merged dataframe containing all relevant summary statistics.
    map_file: Input file containing summary statistic paths + pop and pheno data.

    Returns:
    R_phen: Empirical estimates of genetic correlation across phenotypes.

    """

    if K == 1:
        return np.ones((K, K))
    df, pop_pheno_tuples = filter_for_phen_corr(df, map_file)
    if len(df) == 0:
        print("")
        print(Fore.RED + "WARNING: No files specified for R_phen generation.")
        print("Assuming independent effects." + Style.RESET_ALL)
        return np.diag(np.ones(K))
    phen_corr = build_phen_corr(S, K, pops, phenos, df, pop_pheno_tuples)
    R_phen = np.zeros((K, K))
    for k1 in range(K):
        for k2 in range(K):
            if k1 == k2:
                R_phen[k1, k2] = 1
            elif k1 > k2:
                R_phen[k1, k2] = R_phen[k2, k1]
            else:
                phenos_to_remove = list(set(range(K)) - set([k1, k2]))
                indices_to_remove = collections.deque([])
                for pheno_to_remove in phenos_to_remove:
                    indices_to_remove.extend(
                        [pheno_to_remove + K * x for x in range(S)]
                    )
                pairwise_corrs = delete_rows_and_columns(phen_corr, indices_to_remove)
                R_phen[k1, k2] = np.nanmedian(pairwise_corrs)
    R_phen = np.nan_to_num(R_phen)
    return R_phen


def calculate_err(a, b, pop1, pheno1, pop2, pheno2, err_corr, err_df):

    """
    Calculates a single entry in the err_corr matrix.

    Parameters:
    a, b: Positional parameters within the err_corr matrix.
    pop1: Name of first population.
    pheno1: Name of first phenotype.
    pop2: Name of second population.
    pheno2: Name of second phenotype.
    err_corr: The err_corr matrix thus far.
    err_df: Dataframe containing null, common, LD-independent variants.

    Returns:
    err_corr[a, b]: One entry in the err_corr matrix.

    """

    # If in lower triangle, do not compute; symmetric matrix
    if a > b:
        return err_corr[b, a]
    elif a == b:
        return 1
    else:
        err_df = err_df.dropna()
        err_beta1, err_beta2 = get_betas(err_df, pop1, pheno1, pop2, pheno2, "null")
        if err_beta1:
            corr, p = scipy.stats.pearsonr(err_beta1, err_beta2)
            return corr if (p <= 0.01) else 0
        return 0


def filter_for_err_corr(df, map_file):

    """
    Filters the initial dataframe for the criteria used to build err_corr.

    Parameters:
    df: Merged dataframe containing all summary statistics.
    map_file: Input file containing summary statistic paths + pop and pheno data.

    Returns:
    df: Filtered dataframe that contains null, common, LD-independent variants.

    """

    print("")
    print(Fore.MAGENTA + "Building R_phen and matrix of correlations of errors..." + Style.RESET_ALL)
    print("")
    pop_pheno_tuples = zip(list(map_file["study"]), list(map_file["pheno"]))
    cols_to_keep = collections.deque(["V", "maf", "ld_indep", "most_severe_consequence"])
    for col_type in "BETA_", "P_":
        cols_to_keep.extend(
            [col_type + pop + "_" + pheno for pop, pheno in pop_pheno_tuples]
        )
    df = df[cols_to_keep]
    # Get only LD-independent, common variants
    df = df[(df.maf >= 0.01) & (df.ld_indep == "True")]
    df = df.dropna(axis=1, how="all")
    null_variants = [
        "regulatory_region_variant",
        "non_coding_transcript_variant",
        "mature_miRNA_variant",
        "NMD_transcript_variant",
        "intergenic_variant",
        "upstream_gene_variant",
        "downstream_gene_variant",
        "TF_binding_site_variant",
        "non_coding_transcript_exon_variant",
        "regulatory_region_ablation",
        "TFBS_ablation",
        "NA",
    ]
    # Get only null variants to build err_corr
    if len(df) != 0:
        df = df[df.most_severe_consequence.isin(null_variants)]
    return df


def build_err_corr(S, K, pops, phenos, df, map_file):

    """
    Builds out a matrix of correlations between all phenotypes and studies using:
        - null (i.e. synonymous or functionally uninteresting)
        - not significant (P >= 1e-2)
        - common (MAF >= 0.01)
        - LD independent
    SNPs.

    Parameters:
    S: Number of populations/studies.
    K: Number of phenotypes.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    df: Merged dataframe containing all relevant summary statistics.
    map_file: Input file containing summary statistic paths + pop and pheno data.

    Returns:
    err_corr: (S*K x S*K) matrix of correlation of errors across studies and phenotypes
        for null variants. Used to calculate v_beta.

    """
    if K == 1 and S == 1:
        return np.ones((S * K, S * K))
    err_df = filter_for_err_corr(df, map_file)
    if len(err_df) == 0:
        print(Fore.RED + "WARNING: Correlation of errors is noisy.")
        print("Assuming independent effects." + Style.RESET_ALL)
        print("")
        return np.diag(np.ones(S * K))
    err_corr = np.zeros((S * K, S * K))
    for i, pop1 in enumerate(pops):
        for j, pheno1 in enumerate(phenos):
            for x, pop2 in enumerate(pops):
                for y, pheno2 in enumerate(phenos):
                    # Location in matrix
                    a, b = K * i + j, K * x + y
                    err_corr[a, b] = calculate_err(
                        a, b, pop1, pheno1, pop2, pheno2, err_corr, err_df
                    )
    err_corr = np.nan_to_num(err_corr)
    return err_corr


def return_err_and_R_phen(df, pops, phenos, S, K, map_file):

    """
    Builds a matrix of correlations of errors across studies and phenotypes,
        and correlations of phenotypes.

    Parameters:
    df: Dataframe that containa summary statistics.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    S: Number of populations/studies.
    K: Number of phenotypes.
    map_file: Input file containing summary statistic paths + pop and pheno data.

    Returns:
    err_corr: (S*K x S*K) matrix of correlation of errors across studies and phenotypes
        for null variants. Used to calculate v_beta.
    R_phen: Empirical estimates of genetic correlation across phenotypes.

    """
    # Sample common variants, stuff in filter + synonymous
    err_corr = build_err_corr(S, K, pops, phenos, df, map_file)
    # Faster calculations, better accounts for uncertainty in estimates
    err_corr[abs(err_corr) < 0.01] = 0
    R_phen = build_R_phen(S, K, pops, phenos, df, map_file)
    R_phen[abs(R_phen) < 0.01] = 0
    # Get rid of any values above 0.95
    while np.max(R_phen - np.eye(len(R_phen))) > 0.9:
        R_phen = 0.9 * R_phen + 0.1 * np.diag(np.diag(R_phen))
    return err_corr, R_phen


def se_filter(df, se_thresh, pops, phenos):

    """
    Returns the dataframe filtered for the desired SE threshold.

    Parameters:
    df: Input dataframe (from summary statistics).
    se_thresh: Upper threshsold for SE for this run.
    pops: List of studies from which the current summary statistic dataframe comes from.
    phenos: List of phenotypes from which the current summary statistic dataframe comes from.

    Returns:
    se_df: Dataframe filtered for SE.

    """

    se_cols = ["SE_" + pop + "_" + pheno for pop in pops for pheno in phenos]
    df["min_SE"] = df[se_cols].apply(np.nanmin, axis=1)
    return df.loc[(df["min_SE"] <= se_thresh), ]
    # return df[df["min_SE"] <= se_thresh]


def rename_columns(df, pop, pheno):

    """
    Renames columns such that information on population/study and phenotype is available
        in the resultant dataframe.

    Parameters:
    df: Input dataframe (from summary statistics).
    pop: The study from which the current summary statistic dataframe comes from.
    pheno: The phenotype from which the current summary statistic dataframe comes from.

    Returns:
    df: A df with adjusted column names, e.g., "OR_white_british_cancer1085".

    """

    columns_to_rename = ["BETA", "SE", "P"]
    renamed_columns = [(x + "_" + pop + "_" + pheno) for x in columns_to_rename]
    df.rename(columns=dict(zip(columns_to_rename, renamed_columns)), inplace=True)
    return df


def check_map_file(map_file):

    """
    Checks --file for malformed input.

    Parameters:
    map_file: Input file containing summary statistic paths + pop and pheno data.

    Returns:
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    S: Number of populations/studies.
    K: Number of phenotypes.

    """
    if map_file.isnull().values.sum() > 0:
        raise ValueError("NaNs in map file.")
    file_paths = np.unique(list(map_file["path"]))
    booleans = np.unique(list(map_file["R_phen"]))
    valid_booleans = ["TRUE", "FALSE"]
    if len(file_paths) < len(map_file):
        raise ValueError("File specified in map file contains duplicate path entries.")
    for file_path in file_paths:
        if not os.path.exists(file_path):
            raise IOError("File " + file_path + ", listed in map file does not exist.")
    if (map_file.groupby(["study", "pheno"]).size() > 1).sum() > 0:
        raise ValueError(
            "Multiple summary statistic files specified for a (study, phenotype) tuple."
        )
    for boolean in booleans:
        if boolean.upper() not in valid_booleans:
            raise ValueError(
                "One or more booleans provided in the R_phen column of the map file is not a case-insensitive TRUE/FALSE."
            )
    pops = sorted(list(set(map_file["study"])))
    phenos = sorted(list(set(map_file["pheno"])))
    S = len(pops)
    K = len(phenos)
    return pops, phenos, S, K


def merge_dfs(sumstat_files, metadata_path, sigma_m_types):

    """
    Performs an outer merge on all of the files that have been read in;
    Annotates with metadata and sigma values.

    Parameters:
    sumstat_files: List of dataframes that contain summary statistics.
    metadata_path: Path to metadata file containing MAF, Gene symbol, etc.
    sigma_m_types: Unique list of sigma_m types ("sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005")
        to use for analysis.

    Returns:
    df: Dataframe that is ready for err_corr/R_phen generation and for running MRP.

    """

    print("")
    print(Fore.CYAN + "Merging summary statistics together..." +  Style.RESET_ALL)
    outer_merge = partial(pd.merge, on=["V"], how="outer")
    df = reduce(outer_merge, sumstat_files)
    dtypes = {
        "V": str,
        "most_severe_consequence": str,
        "maf": float,
        "gene_symbol": str,
        "MPC": float,
        "pLI": str,
        "ld_indep": str,
    }
    metadata = pd.read_csv(
        metadata_path,
        sep="\t",
        usecols=list(dtypes.keys()),
        dtype=dtypes,
    )
    metadata = metadata[metadata["V"].isin(list(df["V"]))]
    print(Fore.CYAN + "Merging with metadata..." +  Style.RESET_ALL)
    df = df.merge(metadata)
    del metadata
    print(Fore.CYAN + "Setting sigmas..." +  Style.RESET_ALL)
    df = set_sigmas(df, sigma_m_types)
    gc.collect()
    return df


def read_in_summary_stat(file_path, build, chrom):

    """
    Reads in one summary statistics file.

    Additionally: apply filters (look at ERRCODE column if available, removal of the MHC region, remove variants with null SE, focus on the specified chromosomes), adds a variant identifier ("V")

    Parameters:
    file_path: Path to the summary statistics file.
    pop: Population of interest.
    pheno: Phenotype of interest.
    build: Genome build (hg19 or hg38).
    chrom: List of chromosomes (optional) from command line.

    Returns:
    df: Dataframe with renamed columns, ready for merge.

    """
    df_top = pd.read_csv(file_path, sep="\t", nrows=0)
    se_col = "LOG(OR)_SE" if "LOG(OR)_SE" in df_top.columns else "SE"
    beta_col = "BETA" if "BETA" in df_top.columns else "OR"

    dtypes = {
        "#CHROM": str,
        "POS": np.int32,
        "REF": str,
        "ALT": str,
        beta_col: float,
        se_col: float,
        "P": str,
    }
    if('ERRCODE' in df_top.columns):
        dtypes.update({'ERRCODE': str})
    cols = list(dtypes.keys())

    df = pd.read_csv(
        file_path, sep="\t", usecols=cols, dtype=dtypes,
    )
    df.rename(columns={"#CHROM": "CHROM"}, inplace=True)
    if('ERRCODE' in df.columns):
        df = df[df["ERRCODE"] == "."]
        df = df.drop(columns=["ERRCODE"])
    if se_col == "LOG(OR)_SE":
        df.rename(columns={"LOG(OR)_SE": "SE"}, inplace=True)
    if beta_col == "OR":
        df["BETA"] = np.log(df["OR"].astype("float64"))
        df = df.drop(columns=["OR"])
    if chrom:
        df = df[df['#CHROM'].isin(chrom)]
    # Filter for SE as you read it in
    df = df[df['SE'].notnull()]
    # Filter out HLA region
    HLA_region = {
        'hg19': (25477797, 36448354),
        'hg38': (25477569, 36480577)
    }
    df = df[~(
        (df["CHROM"] == '6') &
        (df["POS"].between( HLA_region[build][0], HLA_region[build][1] ))
    )]
    df["P"] = df["P"].astype(float)
    df.insert(
        loc=0,
        column="V",
        value=df["CHROM"]
        .astype(str)
        .str.cat(df["POS"].astype(str), sep=":")
        .str.cat(df["REF"], sep=":")
        .str.cat(df["ALT"], sep=":"),
    )
    df = df[["V", "BETA", "SE", "P"]]
    gc.collect()
    return df


def read_in_summary_stats(map_file, metadata_path, exclude_path, sigma_m_types, build, chrom):

    """
    Reads in summary statistics.

    Additionally: adds a variant identifier ("V"), renames columns, and filters on
        SE (<= 0.5).

    Contains logic for handling the case that a summary statistic file is not found.

    Parameters:
    map_file: Input file containing summary statistic paths + pop and pheno data.
    metadata_path: Path to metadata file containing MAF, Gene symbol, etc.
    exclude_path: Path to file containing list of variants to exclude from analysis.
    sigma_m_types: Unique list of sigma_m types ("sigma_m_mpc_pli"/"sigma_m_var"/"sigma_m_1"/"sigma_m_005")
        to use for analysis.
    build: Genome build (hg19 or hg38).
    chrom: List of chromosomes (optional) from command line.

    Returns:
    df: Merged summary statistics.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    S: Number of populations/studies.
    K: Number of phenotypes.

    """

    pops, phenos, S, K = check_map_file(map_file)
    print(Fore.CYAN + "Map file passes initial checks.")
    print("")
    print("Reading in summary statistics for:")
    print("")
    print("Populations: " + Style.RESET_ALL + ", ".join(pops))
    print(Fore.CYAN + "Phenotypes: " + Style.RESET_ALL + ", ".join(phenos))
    print("")
    sumstat_files = collections.deque([])
    for pop in pops:
        for pheno in phenos:
            subset_df = map_file[(map_file.study == pop) & (map_file.pheno == pheno)]
            if len(subset_df) == 1:
                file_path = list(subset_df["path"])[0]
                df = read_in_summary_stat(file_path, build, chrom)
                print(
                    '{pop} {pheno} {nrow}x{ncol} {path}'.format(
                        pop=pop, pheno=pheno, nrow = df.shape[0], ncol = df.shape[1], path = file_path
                    )
                )
                sumstat_files.append(rename_columns(df, pop, pheno))
            else:
                print(
                    Fore.RED
                    + "WARNING: A summary statistic file cannot be found for "
                    + "population: {}; phenotype: {}.".format(pop, pheno)
                    + Style.RESET_ALL
                )
    try:
        if exclude_path:
            exclude_path = exclude_path[0]
            variants_to_exclude = [line.rstrip("\n") for line in open(exclude_path)]
    except:
        raise IOError("Could not open exclusions file (--exclude).")
    df = merge_dfs(sumstat_files, metadata_path, sigma_m_types)
    del(sumstat_files)
    if exclude_path:
        df = df[~df["V"].isin(variants_to_exclude)]
    gc.collect()
    print(
        'summary statistics df: {nrow}x{ncol}'.format(
            nrow = df.shape[0], ncol = df.shape[1]
        )
    )
    return df, pops, phenos, S, K


def print_banner():

    """
    Prints ASCII Art Banner + Author Info.

    """

    print("")
    print(Fore.RED + " __  __ ____  ____")
    print("|  \/  |  _ \|  _ \\")
    print("| |\/| | |_) | |_) |")
    print("| |  | |  _ <|  __/ ")
    print("|_|  |_|_| \_\_|  " + Style.RESET_ALL)
    print("")
    print(Fore.GREEN + "Production Author:" + Style.RESET_ALL)
    print("Guhan Ram Venkataraman, B.S.H.")
    print("Ph.D. Candidate | Biomedical Informatics")
    print("")
    print(Fore.GREEN + "Contact:" + Style.RESET_ALL)
    print("Email: guhan@stanford.edu")
    print(
        "URL: https://github.com/rivas-lab/mrp"
    )
    print("")
    print(Fore.GREEN + "Methods Developers:" + Style.RESET_ALL)
    print("Manuel A. Rivas, Ph.D.; Matti Pirinen, Ph.D.")
    print("Rivas Lab | Stanford University")


def return_input_args(args):

    """
    Further parses the command-line input.

    Makes all lists unique; calculates S and K; and creates lists of appropriate
        matrices.

    Parameters:
    args: Command-line arguments that have been parsed by the parser.

    Returns:
    df: Merged summary statistics.
    map_file: Input file containing summary statistic paths + pop and pheno data.
    S: Number of populations/studies.
    K: Number of phenotypes.
    pops: Unique set of populations (studies) to use for analysis.
    phenos: Unique set of phenotypes to use for analysis.
    R_study: Unique list of R_study matrices to use for analysis.

    """

    try:
        map_file = pd.read_csv(
            args.map_file,
            sep="\t",
            dtype={"path": str, "pop": str, "pheno": str, "R_phen": str},
        )
    except:
        raise IOError("File specified in --file does not exist.")
    df, pops, phenos, S, K = read_in_summary_stats(
        map_file, args.metadata_path, args.exclude, args.sigma_m_types, args.build, args.chrom
    )
    for arg in vars(args):
        if (arg != "filter_ld_indep") and (arg != "mean"):
            setattr(args, arg, sorted(list(set(getattr(args, arg)))))
    R_study = [
        np.diag(np.ones(S)) if x == "independent" else np.ones((S, S))
        for x in args.R_study_models
    ]
    return (df, map_file, S, K, pops, phenos, R_study)


def range_limited_float_type(arg):

    """
    Type function for argparse - a float within some predefined bounds.

    Parameters:
    arg: Putative float.

    Returns:
    f: The same float, if a valid floating point number between 0 and 1.

    """

    try:
        f = float(arg)
    except ValueError:
        raise argparse.ArgumentTypeError("must be valid floating point numbers.")
    if f <= 0 or f > 1:
        raise argparse.ArgumentTypeError("must be > 0 and <= 1.")
    return f


def positive_float_type(arg):

    """
    Type function for argparse - a float that is positive.

    Parameters:
    arg: Putative float.

    Returns:
    f: The same float, if positive.

    """

    try:
        f = float(arg)
    except ValueError:
        raise argparse.ArgumentTypeError("must be valid floating point numbers.")
    if f < 0:
        raise argparse.ArgumentTypeError("must be >= 0.")
    return f


def initialize_parser():

    """
    Parses inputs using argparse.

    """

    parser = argparse.ArgumentParser(
        description="MRP takes in several variables that affect how it runs.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        dest="map_file",
        help="""path to tab-separated file containing list of:
         summary statistic file paths,
         corresponding studies,
         phenotypes, and
         whether or not to use the file in R_phen generation.

         format:

         path        study        pheno        R_phen
         /path/to/file1   study1    pheno1     TRUE
         /path/to/file2   study2    pheno1     FALSE
         """,
    )
    parser.add_argument(
        "--metadata_path",
        type=str,
        required=True,
        dest="metadata_path",
        help="""path to tab-separated file containing:
         variants,
         gene symbols,
         consequences,
         MAFs,
         and LD independence info.

         format:

         V       gene_symbol     most_severe_consequence maf  ld_indep
         1:69081:G:C     OR4F5   5_prime_UTR_variant     0.000189471     False
        """,
    )
    parser.add_argument(
        "--build",
        choices=["hg19", "hg38"],
        type=str,
        required=True,
        dest="build",
        help="""genome build (hg19 or hg38). Required.""",
    )
    parser.add_argument(
        "--chrom",
        choices=["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20","21","22","X","Y"],
        type=str,
        nargs="+",
        dest="chrom",
        default=[],
        help="""chromosome filter. options include 1-22, X, and Y""",
    )
    parser.add_argument(
        "--mean",
        type=float,
        nargs=1,
        dest="mean",
        default=0,
        help="""prior mean of genetic effects (Default: 0).""",
    )
    parser.add_argument(
        "--R_study",
        choices=["independent", "similar"],
        type=str,
        nargs="+",
        default=["similar"],
        dest="R_study_models",
        help="""type of model across studies.
         options: independent, similar (default: similar). can run both.""",
    )
    parser.add_argument(
        "--R_var",
        choices=["independent", "similar"],
        type=str,
        nargs="+",
        default=["independent"],
        dest="R_var_models",
        help="""type(s) of model across variants.
         options: independent, similar (default: independent). can run both.""",
    )
    parser.add_argument(
        "--M",
        choices=["variant", "gene"],
        type=str,
        nargs="+",
        default=["gene"],
        dest="agg",
        help="""unit(s) of aggregation.
         options: variant, gene (default: gene). can run both.""",
    )
    parser.add_argument(
        "--sigma_m_types",
        choices=["sigma_m_mpc_pli", "sigma_m_var", "sigma_m_1", "sigma_m_005"],
        type=str,
        nargs="+",
        default=["sigma_m_mpc_pli"],
        dest="sigma_m_types",
        help="""scaling factor(s) for variants.
         options: var (i.e. 0.2 for ptvs, 0.05 for pavs/pcvs),
         1, 0.05 (default: mpc_pli). can run multiple.""",
    )
    parser.add_argument(
        "--variants",
        choices=["pcv", "pav", "ptv", "all"],
        type=str,
        nargs="+",
        default=["ptv"],
        dest="variant_filters",
        help="""variant set(s) to consider.
         options: proximal coding [pcv],
                  protein-altering [pav],
                  protein truncating [ptv],
                  all variants [all]
                  (default: ptv). can run multiple.""",
    )
    parser.add_argument(
        "--maf_thresh",
        type=range_limited_float_type,
        nargs="+",
        default=[0.01],
        dest="maf_threshes",
        help="""which MAF threshold(s) to use. must be valid floats between 0 and 1
         (default: 0.01).""",
    )
    parser.add_argument(
        "--se_thresh",
        type=positive_float_type,
        nargs="+",
        default=[0.2],
        dest="se_threshes",
        help="""which SE threshold(s) to use. must be valid floats between 0 and 1
         (default: 0.2). NOTE: This strict default threshold is best suited for binary
         summary statistics. For quantitative traits, we suggest the use of a higher
         threshold.""",
    )
    parser.add_argument(
        "--prior_odds",
        type=range_limited_float_type,
        nargs="+",
        default=[0.0005],
        dest="prior_odds_list",
        help="""which prior odds (can be multiple) to use in calculating posterior
         probabilities. must be valid floats between 0 and 1 (default: 0.0005, expect
         1 in 2000 genes to be a discovery).""",
    )
    parser.add_argument(
        "--p_value",
        choices=["farebrother", "davies", "imhof"],
        type=str,
        nargs="+",
        default=[],
        dest="p_value_methods",
        help="""which method(s) to use to convert Bayes Factors to p-values. if command
         line argument is invoked but method is not specified, will throw an error
         (i.e., specify a method when it is invoked). if not invoked, p-values will not
         be calculated. options: farebrother, davies, imhof. NOTE: --p_value imports R
         objects and methods, which slows down MRP. farebrother is fastest and
         recommended if p-values are a must.""",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs=1,
        default=[],
        dest="exclude",
        help="""path to file containing list of variants to exclude from analysis.

         format of file:

         1:69081:G:C
         1:70001:G:A
        """,
    )
    parser.add_argument(
        "--filter_ld_indep",
        action="store_true",
        dest="filter_ld_indep",
        help="""whether or not only ld-independent variants should be kept (default: False;
         i.e., use everything).""",
    )
    parser.add_argument(
        "--out_folder",
        type=str,
        nargs=1,
        default=[],
        dest="out_folder",
        help="""folder to which output(s) will be written (default: current folder).
         if folder does not exist, it will be created.""",
    )
    parser.add_argument(
        "--out_filename",
        type=str,
        nargs=1,
        default=[],
        dest="out_filename",
        help="""file prefix with which output(s) will be written (default: underscore-delimited
         phenotypes).""",
    )
    return parser


def mrp_main():
    """
    Runs MRP analysis on summary statistics with the parameters specified
        by the command line.

    """

    parser = initialize_parser()
    args = parser.parse_args()
    print_banner()
    print("")
    print("Valid command line arguments. Importing required packages...")
    print("")

    if args.p_value_methods:
        print("")
        print(
            Fore.RED
            + "WARNING: Command line arguments indicate p-value generation. "
            + "This can cause slowdowns of up to 12x."
        )
        print(
            "Consider using --prior_odds instead to generate posterior probabilities"
            + " as opposed to p-values."
            + Style.RESET_ALL
        )
        import rpy2
        import rpy2.robjects as robjects
        import rpy2.robjects.numpy2ri

        rpy2.robjects.numpy2ri.activate()
        import rpy2.robjects.packages as rpackages
        from rpy2.robjects.vectors import StrVector
        from rpy2.robjects.vectors import ListVector
        from rpy2.robjects.vectors import FloatVector
        import warnings
        from rpy2.rinterface import RRuntimeWarning

        warnings.filterwarnings("ignore", category=RRuntimeWarning)

    df, map_file, S, K, pops, phenos, R_study_list = return_input_args(args)
    if args.filter_ld_indep:
        df = df[df["ld_indep"] == "True"]
    for se_thresh in args.se_threshes:
        se_df = se_filter(df, se_thresh, pops, phenos)
        out_folder = args.out_folder[0] if args.out_folder else os.getcwd()
        out_filename = args.out_filename[0] if args.out_filename else []
        err_corr, R_phen = return_err_and_R_phen(
            se_df, pops, phenos, len(pops), len(phenos), map_file
        )
        print("Correlation of errors, SE threshold = " + str(se_thresh) + ":")
        print(err_corr)
        print("")
        print("R_phen:")
        print(R_phen)
        print("")
        loop_through_parameters(
            se_df,
            se_thresh,
            args.maf_threshes,
            args.agg,
            args.variant_filters,
            S,
            R_study_list,
            args.R_study_models,
            pops,
            K,
            R_phen,
            phenos,
            args.R_var_models,
            args.sigma_m_types,
            err_corr,
            args.prior_odds_list,
            args.p_value_methods,
            out_folder,
            out_filename,
            args.mean,
            args.chrom,
        )


if __name__ == "__main__":
    start = time.time()
    mrp_main()
    end = time.time()
    print(
        Fore.CYAN +
        'MRP analysis finished. Total elapsed time: {:.2f} [s]'.format(
            end - start
        ) + Style.RESET_ALL
    )
