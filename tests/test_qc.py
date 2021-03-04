# -*- coding: utf-8 -*-

import pandas as pd
import pytest

from bio_hansel.qc import is_maybe_intermediate_subtype
from bio_hansel.qc.const import QC
from bio_hansel.subtype import Subtype
from bio_hansel.subtyper import subtype_reads, subtype_contigs
from bio_hansel.utils import init_subtyping_params

genome_name = 'test'


def test_low_coverage():
    scheme = 'heidelberg'
    fastq = 'tests/data/SRR1696752/SRR1696752.fastq'
    st, df = subtype_reads(reads=fastq, genome_name=genome_name, scheme=scheme)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.is_fastq_input()
    assert st.scheme == scheme
    assert 'Low coverage for all kmers (7.439 < 20 expected)' in st.qc_message
    assert st.qc_status == QC.FAIL


def test_intermediate_subtype():
    scheme = 'enteritidis'
    st = Subtype(sample='test',
                 file_path='tests/data/Retro1000data/10-1358.fastq',
                 scheme='enteritidis',
                 scheme_version='1.0.5',
                 subtype='2.1.1.2',
                 non_present_subtypes=[],
                 all_subtypes='2; 2.1; 2.1.1; 2.1.1.2',
                 inconsistent_subtypes=None,
                 kmers_matching_subtype='308238-2.1.1.2; 2469336-2.1.1.2; 3872935-2.1.1.2',
                 negative_kmers_matching_subtype=None,
                 are_subtypes_consistent=True,
                 n_kmers_matching_all=183,
                 n_kmers_matching_positive=12,
                 n_kmers_matching_negative=171,
                 n_kmers_matching_subtype=3,
                 n_kmers_matching_all_expected='188',
                 n_kmers_matching_positive_expected='15',
                 n_kmers_matching_negative_expected=0,
                 n_kmers_matching_subtype_expected='6',
                 n_negative_kmers_matching_subtype_expected=0,
                 avg_kmer_coverage=37.04102564102564,
                 qc_status=None,
                 qc_message=None)
    df = pd.read_csv('tests/data/se_intermediate_subtype_df.csv')
    p = init_subtyping_params(args=None, scheme=scheme)
    st.qc_status, st.qc_message = is_maybe_intermediate_subtype(st, df, p)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.scheme == scheme
    assert "Total subtype matches observed (n=3) vs expected (n=6)" in st.qc_message
    assert st.qc_status == QC.WARNING


def test_missing_kmers():
    scheme = 'heidelberg'
    fastq = 'tests/data/SRR1696752/SRR1696752.fastq'
    st, df = subtype_reads(reads=fastq, genome_name=genome_name, scheme=scheme)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.is_fastq_input()
    assert st.scheme == scheme
    assert 'Low coverage depth (10.9 < 20.0 expected)' in st.qc_message
    assert st.qc_status == QC.FAIL


def test_mixed_kmers():
    scheme = 'heidelberg'
    fastqs = ['tests/data/SRR3392166/SRR3392166.fastq', 'tests/data/SRR3392166/SRR3392166.fastq']
    st, df = subtype_reads(reads=fastqs, genome_name=genome_name, scheme=scheme)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.scheme == scheme
    assert 'Mixed subtypes found: "1; 2; 2.1"' in st.qc_message
    assert st.qc_status == QC.FAIL


def test_mixed_subtype_positive_negative_kmers_same_target():
    scheme = 'heidelberg'
    fasta = 'tests/data/fail-qc-mixed-subtype-pos-neg-kmers.fasta'
    st, df = subtype_contigs(fasta_path=fasta, genome_name=genome_name, scheme=scheme)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.scheme == scheme
    assert st.qc_status == QC.FAIL
    expected_qc_msg = ('FAIL: Mixed subtype; the positive and negative kmers were found for the same '
                       'target sites 202001, 600783, 1049933, 1193219, 2778621, 2904061, '
                       '3278067, 3867228, 4499501, 4579224, 4738855, 202001, '
                       '600783, 1049933, 1193219, 2778621, 2904061, 3278067, '
                       '3867228, 4499501, 4579224, 4738855 for subtype "1.1".')
    assert expected_qc_msg in st.qc_message


def test_unconfident_subtype():
    scheme = 'enteritidis'
    fasta = 'tests/data/fail-qc-unconfident-subtype.fasta'
    st, df = subtype_contigs(fasta_path=fasta, genome_name=genome_name, scheme=scheme)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.scheme == scheme
    assert st.qc_status == QC.FAIL
    assert QC.UNCONFIDENT_RESULTS_ERROR_4 in st.qc_message
    assert "kmers for downstream subtype(s)" in st.qc_message
    assert "'2.1.5.4.2'" in st.qc_message
    assert "'2.1.5.4.1'" in st.qc_message


def test_missing_hierarchy_levels_in_subtype():
    scheme = 'heidelberg'
    fasta = 'tests/data/fail-qc-missing-levels.fasta'
    st, df = subtype_contigs(fasta_path=fasta, genome_name=genome_name, scheme=scheme)
    assert isinstance(st, Subtype)
    assert isinstance(df, pd.DataFrame)
    assert st.scheme == scheme
    assert st.qc_status == QC.FAIL
    assert QC.UNCONFIDENT_RESULTS_ERROR_4 in st.qc_message
    assert "kmers for nested hierarchical subtype(s)" in st.qc_message
    assert "2.1" in st.qc_message
    assert "2.1.1" in st.qc_message


def test_too_many_kmers():
    import bio_hansel.utils
    with pytest.raises(ValueError):
        scheme = 'tests/data/too_many_kmers.fasta'
        assert bio_hansel.utils.check_total_kmers(scheme, 100000)
