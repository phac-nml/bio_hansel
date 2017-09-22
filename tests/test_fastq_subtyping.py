import pytest
from pandas import DataFrame
from bio_hansel.subtype import Subtype
from bio_hansel.subtyper import subtype_reads
from bio_hansel.utils import SCHEME_FASTAS


@pytest.fixture
def test_genome():
    return 'tests/data/SRR5646583_SMALL.fastq'


def test_fastq_subtyping(test_genome):
    genome_name = 'test'
    scheme = 'heidelberg'
    st, df = subtype_reads(scheme='heidelberg', reads=test_genome, genome_name=genome_name, threads=4)
    assert isinstance(st, Subtype)
    assert isinstance(df, DataFrame)

    assert st.scheme == scheme
    assert st.scheme_version == SCHEME_FASTAS[scheme]['version']
    assert st.sample == genome_name
    assert st.subtype == '2.2.1.1.1.1'
    assert st.are_subtypes_consistent is True
    assert st.inconsistent_subtypes is None
    assert st.n_tiles_matching_all == 202
    assert st.n_tiles_matching_all_total == '202'
    assert st.n_tiles_matching_positive == 20
    assert st.n_tiles_matching_positive_total == '20'
    assert st.n_tiles_matching_subtype == 2
    assert st.n_tiles_matching_subtype_total == '2'
