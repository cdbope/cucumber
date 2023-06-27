"""Console script for cucumber."""
import numpy as np
import pandas as pd
from enum import Enum
import time
import os
from matplotlib import pyplot as plt
import seaborn as sns
import string
import bionumpy as bnp
from numpy import linalg as LA
from scipy import stats
import scipy.spatial as sp
from scipy.optimize import linear_sum_assignment

np.random.seed(10000)


# todo

class DataType(str, Enum):
    exome = 'exome'
    genome = 'genome'


import typer
from .refit import refit as _refit
from .denovo import denovo as _denovo, cos_sim_matrix
from .count_mutation_cli import count_mutation
from .bootstrapping import bootstrap as _bootstrap


def bootstrap(matrix_file: str, signature_file: str, output_file_exposure_avg: str, output_file_exposure_std: str,
              opportunity_file: str = None, data_type: DataType = DataType.exome):
    M = read_counts(matrix_file)
    S, index_signature = read_signature(signature_file)
    O = read_opportunity(M, opportunity_file)
    lambd = get_lambda(data_type)
    estimated_exposure, exposure_std = _bootstrap(M, S, O, lambd=lambd)
    np.savetxt(output_file_exposure_avg, estimated_exposure, delimiter='\t')
    np.savetxt(output_file_exposure_std, exposure_std, delimiter='\t')


def plot(file):
    plt.style.use('default')
    file.plot(kind="bar", figsize=(10, 4))
    plt.xticks(fontsize=8)
    plt.yticks(fontsize=8)
    plt.ylabel("Mutation fraction")
    plt.xlabel("Signatures")
    plt.tight_layout()
    return plt.savefig("output/plot_cohort.png", dpi=600)


def singleplot(file):
    file = file.transpose()
    file.columns = ['Signatures', 'std_dev']
    filtered_data = file[file['Signatures'] != 0]

    # Set up the figure and axis
    plt.style.use('default')
    fig, ax = plt.subplots()
    fig, ax = plt.subplots(figsize=(20, 8))

    # Plot the bar plot with error bars for non-zero values
    ax.bar(filtered_data.index, filtered_data['Signatures'], yerr=filtered_data['std_dev'],
           color='blue', alpha=0.5, align='center', capsize=3)
    plt.ylim(0, None)
    plt.xticks(rotation=45)
    plt.xticks(fontsize=8)
    plt.yticks(fontsize=8)
    plt.xticks(rotation=45)
    # Set labels and title
    ax.set_xlabel('Signature exposures')
    ax.set_ylabel('Mutation fraction')
    ax.set_title('Single Sample Mutational Signatures')
    return plt


def cohortplot(file):
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(20, 8))
    file.plot(kind="bar", figsize=(10, 4))
    plt.xticks(rotation=45)
    plt.xticks(fontsize=7)
    plt.yticks(fontsize=7)
    plt.ylabel("Mutation fraction")
    plt.xlabel("Signature exposures")
    plt.tight_layout()
    return plt

def cohort_violin(file):
    fig, ax = plt.subplots(figsize=(20, 8))
    sns.violinplot(data=file, ax=ax, scale="count", cut=0)
    plt.xticks(rotation=45)
    plt.xticks(fontsize=8)
    plt.yticks(fontsize=8)
    plt.ylabel("Mutation fraction")
    plt.xlabel("Signature exposures")
    return plt


def refit(matrix_file: str, signature_file: str, output_file_exposure: str,
          opportunity_file: str = None,
          data_type: DataType = DataType.exome, n_bootstraps: int = 100, numeric_chromosomes: bool = False,
          genotyped: bool = True,
          output_file_exposure_avg=None):
    '''
    Parameters
    ----------
    numeric_chromosomes
    n_bootstraps
    matrix_file: str
    signature_file: str
    output_file_exposure: str
    opportunity_file: str
    data_type: DataType
    numeric_chromosomes: bool
        True if chromosome names in vcf are '1', '2', '3'. False if 'chr1', 'chr2', 'chr3'
    genotyped: bool
        True if the VCF file has genotype information for many samples
    '''
    start_time = time.time()
    ref_genome = '/Users/bope/Documents/MutSig/scientafellow/packages/ref/Homo_sapiens.GRCh38.dna.primary_assembly.fa'
    file_name, file_extension = os.path.splitext(matrix_file)
    if file_extension == '.vcf':
        count_mutation(matrix_file, ref_genome, 'output/matrix.csv', numeric_chromosomes, genotyped)
        matrix_file = 'output/matrix.csv'
    M = read_counts(matrix_file)
    S, index_signature = read_signature(signature_file)
    O = read_opportunity(M, opportunity_file)
    lambd = get_lambda(data_type)
    if (M.ndim == 2 and M.shape[0] == 1) or M.ndim == 1:
        E = _refit(M, S, O, lambd=lambd)[0]
        E_std = _bootstrap(M, S, O, n_bootstraps, lambd=lambd)
        E = [E, E_std]
        E = pd.DataFrame(data=E, columns=index_signature, index=['Signature', 'std_dev'])
        E.drop(columns=E.columns[0], axis=1, inplace=True)
        plot = singleplot(E)
        plot.savefig("output/single_spar2.png", dpi=600)
        E.to_csv(output_file_exposure, index=True, header=True, sep='\t')
    else:
        E = _refit(M, S, O, lambd=lambd)
        sum_expo = E.sum(axis=0, keepdims=True) / len(E)
        E = pd.DataFrame(data=E, columns=index_signature)
        E.to_csv(output_file_exposure, index=False, header=True, sep='\t')
        sum_expo = pd.DataFrame(data=sum_expo, columns=index_signature, index=['Signatures'])
        # print(sum_expo)
        sum_expo = np.transpose(sum_expo)
        plot_summary = cohortplot(sum_expo)
        plot_summary.savefig("output/exposures_cohort_dotplot.png", dpi=600)
        sort_E = sum_expo.sort_values(by=['Signatures'], ascending=False)
        sort_E = sort_E.iloc[:5, 0:]
        plot_top_five = cohortplot(sort_E)
        plot_top_five.savefig("output/exposures_cohort_top_5.png", dpi=600)
        plot_variance = cohort_violin(E)
        plot_variance.savefig("output/exposures_cohort_variance.png", dpi=600)
        sum_expo.to_csv(output_file_exposure_avg, index=index_signature, header=True, sep='\t')
    print("--- %s seconds ---" % (time.time() - start_time))


def get_lambda(data_type):
    if data_type == DataType.genome:
        lambd = 10
    else:
        lambd = 10
    return lambd


def read_opportunity(M, opportunity_file):
    n_samples = len(M)
    n_mutations = M.shape[1]
    if opportunity_file is not None:
        O = pd.read_csv(opportunity_file, sep='\t', header=None).to_numpy().astype(float)
        O = np.broadcast_to(O, M.shape)
    else:
        O = np.ones((n_samples, n_mutations), dtype=float)
    O = O / np.amax(O).sum(axis=-1, keepdims=True)
    assert O.shape == (n_samples, n_mutations), f'{O.shape} != {(n_samples, n_mutations)}'
    return O


def read_signature(signature_file):
    S = pd.read_csv(signature_file, delimiter=',')
    index_signature = S.index.values.tolist()
    S = S.to_numpy().astype(float)
    return S, index_signature


def read_counts(matrix_file):
    return pd.read_csv(matrix_file, delimiter='\t').to_numpy().astype(float)


def denovo(matrix_file: str, n_signatures: int, lambd: float, output_file_exposure: str, output_file_signature: str,
           opportunity_file: str = None, cosmic_file: str = None, max_em_iterations: int = 2,
           max_gd_iterations: int = 50, numeric_chromosomes: bool = False, genotyped: bool = True, file_extension=None,
           ref_genome=None):
    '''
    Parameters
    ----------
    matrix_file: str
    n_signatures: int
    lambd: float
    output_file_exposure: str
    output_file_signature: str
    opportunity_file: str
    cosmic_file: str
    max_em_iterations
    max_gd_iterations
    numeric_chromosomes: bool
        True if chromosome names in vcf are '1', '2', '3'. False if 'chr1', 'chr2', 'chr3'
    genotyped: bool
        True if the VCF file has genotype information for many samples
    '''
    start_time = time.time()
    if file_extension == '.vcf':
        count_mutation(matrix_file, ref_genome, 'output/matrix.csv', numeric_chromosomes, genotyped)
        matrix_file = 'output/matrix.csv'
    M = pd.read_csv(matrix_file, delimiter='\t').to_numpy().astype(float)
    n_samples = len(M)
    n_signatures = n_signatures
    lambd = lambd
    n_mutations = M.shape[1]
    if opportunity_file is not None:
        O = pd.read_csv(opportunity_file, sep='\t', header=None).to_numpy().astype(float)
        O = np.broadcast_to(O, M.shape)
    else:
        O = np.ones((n_samples, n_mutations), dtype=float)
        # print(O)
    O = O / np.amax(O).sum(axis=-1, keepdims=True)
    assert O.shape == (n_samples, n_mutations), f'{O.shape} != {(n_samples, n_mutations)}'
    E, S = _denovo(M, n_signatures, lambd, O, em_steps=max_em_iterations, gd_steps=max_gd_iterations)
    if cosmic_file is not None:
        cosmic = pd.read_csv(cosmic_file, delimiter=',')
        cos_similarity = cos_sim_matrix(S, cosmic)[0]
        cos_similarity.to_csv("output/cos_sim_brca_2_s5_l02_05_2000_te_6_2.txt", sep="\t")
        print(cos_similarity)
    S = np.transpose(S)
    alphabet = list(string.ascii_uppercase)
    Sig = ['Denovo ' + alphabet[k] for k in range(S.shape[1])]
    # print(Sig)
    mutation_labels = ['A[C>A]A', 'A[C>A]C', 'A[C>A]G', 'A[C>A]T', 'C[C>A]A', 'C[C>A]C', 'C[C>A]G', 'C[C>A]T', 'G[C>A]A', 'G[C>A]C', 'G[C>A]G', 'G[C>A]T', 'T[C>A]A', 'T[C>A]C', 'T[C>A]G', 'T[C>A]T', 'A[C>G]A', 'A[C>G]C', 'A[C>G]G', 'A[C>G]T', 'C[C>G]A', 'C[C>G]C', 'C[C>G]G', 'C[C>G]T', 'G[C>G]A', 'G[C>G]C', 'G[C>G]G', 'G[C>G]T', 'T[C>G]A', 'T[C>G]C', 'T[C>G]G', 'T[C>G]T', 'A[C>T]A','A[C>T]C', 'A[C>T]G', 'A[C>T]T', 'C[C>T]A', 'C[C>T]C', 'C[C>T]G', 'C[C>T]T', 'G[C>T]A', 'G[C>T]C', 'G[C>T]G', 'G[C>T]T', 'T[C>T]A', 'T[C>T]C', 'T[C>T]G', 'T[C>T]T', 'A[T>A]A', 'A[T>A]C', 'A[T>A]G','A[T>A]T', 'C[T>A]A', 'C[T>A]C', 'C[T>A]G', 'C[T>A]T', 'G[T>A]A', 'G[T>A]C', 'G[T>A]G','G[T>A]T', 'T[T>A]A', 'T[T>A]C', 'T[T>A]G', 'T[T>A]T', 'A[T>C]A', 'A[T>C]C', 'A[T>C]G', 'A[T>C]T','C[T>C]A', 'C[T>C]C', 'C[T>C]G','C[T>C]T', 'G[T>C]A', 'G[T>C]C', 'G[T>C]G', 'G[T>C]T', 'T[T>C]A', 'T[T>C]C', 'T[T>C]G', 'T[T>C]T', 'A[T>G]A' ,'A[T>G]C', 'A[T>G]G', 'A[T>G]T', 'C[T>G]A','C[T>G]C', 'C[T>G]G', 'C[T>G]T', 'G[T>G]A', 'G[T>G]C', 'G[T>G]G', 'G[T>G]T', 'T[T>G]A' ,'T[T>G]C' ,'T[T>G]G' ,'T[T>G]T']
    label = list(mutation_labels)
    S = pd.DataFrame(S, columns=Sig, index= label)
    S.to_csv("output/d_sig1.txt", sep = '\t' , index = label)
    np.savetxt(output_file_exposure, np.array(E))
    np.savetxt(output_file_signature, np.array(S))
    print("--- %s seconds ---" % (time.time() - start_time))


def main():
    app = typer.Typer()
    app.command()(refit)
    app.command()(denovo)
    app.command()(count_mutation)
    app()


if __name__ == "__main__":
    main()
