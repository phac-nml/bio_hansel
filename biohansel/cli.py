import logging
from typing import Union, Optional, Tuple, List

import attr
import click
import pandas as pd

from biohansel.subtype import subtype_contigs_samples, subtype_reads_samples, Subtype
from biohansel.subtype.const import SUBTYPE_SUMMARY_COLS, JSON_EXT_TMPL
from biohansel.subtype.metadata import read_metadata_table, merge_metadata_with_summary_results
from biohansel.subtype.subtype_stats import subtype_counts
from biohansel.subtype.util import get_scheme_fasta, init_subtyping_params
from biohansel.utils import does_file_exist, collect_inputs
from biohansel.utils import init_console_logger

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
@click.option('-v', '--verbose', count=True,
              help="Logging verbosity (-v for logging warnings; -vvv for logging debug info)")
def cli(verbose):
    """Subtype with a biohansel scheme or create a scheme for your organism of interest
    """
    lvl = init_console_logger(verbose)
    logging.debug('Initialized logging with %s level', lvl)


def check_between_0_and_1_inclusive(ctx: click.Context,
                                    param: click.Option,
                                    value: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
    if value is None or 0.0 <= value <= 1.0:
        return value
    else:
        raise click.BadParameter('value needs to be between 0.0 and 1.0 inclusive!')


def check_positive_number(ctx: click.Context,
                          param: click.Option,
                          value: Optional[Union[int, float]]) -> Optional[Union[int, float]]:
    if value is None or value >= 0:
        return value
    else:
        raise click.BadParameter('value must be 0 or greater!')


@cli.command()
@click.option('-s', '--scheme', default='heidelberg',
              help='Scheme to use for subtyping (built-in: "heidelberg", "enteritidis"; '
                   'OR user-specified: /path/to/user/scheme)')
@click.option('--scheme-name', help='Custom user-specified SNP substyping scheme name')
@click.option('-M', '--scheme-metadata',
              help='Scheme subtype metadata table (CSV or tab-delimited format; must contain "subtype" column)')
@click.option('-p', '--paired-reads',
              metavar='FORWARD_READS REVERSE_READS',
              type=(str, str),
              multiple=True,
              help='FASTQ paired-end reads')
@click.option('-i', '--input-fasta-genome-name',
              metavar='FASTA_PATH GENOME_NAME',
              type=(str, str),
              multiple=True,
              help='fasta file path to genome name pair')
@click.option('-D', '--input-directory',
              type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='directory of input fasta files (.fasta|.fa|.fna) or FASTQ files (paired FASTQ should '
                   'have same basename with "_\d\.(fastq|fq)" postfix to be automatically paired) '
                   '(files can be Gzipped)')
@click.option('-o', '--output-summary-path',
              help='Subtyping summary output path (tab-delimited)')
@click.option('-O', '--output-tile-results',
              help='Subtyping tile matching output path (tab-delimited)')
@click.option('-S', '--output-simple-summary-path',
              help='Subtyping simple summary output path')
@click.option('--force',
              is_flag=True,
              help='Force existing output files to be overwritten')
@click.option('--json-output',
              is_flag=True,
              help='Output JSON representation of output files?')
@click.option('--min-kmer-freq',
              default=None,
              type=int,
              callback=check_positive_number,
              help='Min k-mer freq/coverage')
@click.option('--max-kmer-freq',
              default=None,
              type=int,
              callback=check_positive_number,
              help='Max k-mer freq/coverage')
@click.option('--low-coverage-threshold',
              default=None,
              type=float,
              callback=check_positive_number,
              help='Frequencies below this threshold are considered low coverage')
@click.option('--max-missing-tiles',
              default=None,
              type=float,
              callback=check_between_0_and_1_inclusive,
              help='Decimal proportion of maximum allowable missing tiles before being considered an error. (0.0 - 1.0)')
@click.option('--min-ambiguous-tiles',
              default=None,
              type=int,
              callback=check_positive_number,
              help='Minimum number of missing tiles to be considered an ambiguous result')
@click.option('--low-coverage-warning',
              default=None,
              type=int,
              callback=check_positive_number,
              help='Overall tile coverage below this value will trigger a low coverage warning')
@click.option('--max-intermediate-tiles',
              default=None,
              type=float,
              callback=check_between_0_and_1_inclusive,
              help='Decimal proportion of maximum allowable missing tiles to be considered an intermediate subtype. (0.0 - 1.0)')
@click.option('-t', '--threads',
              type=int,
              default=1,
              help='Number of parallel threads to run analysis (default=1)')
@click.argument('files', type=click.Path(exists=True), nargs=-1)
def subtype(scheme,
            scheme_name,
            scheme_metadata,
            paired_reads,
            input_fasta_genome_name,
            input_directory,
            output_summary_path,
            output_tile_results,
            output_simple_summary_path,
            force,
            json_output,
            min_kmer_freq,
            max_kmer_freq,
            low_coverage_threshold,
            max_missing_tiles,
            min_ambiguous_tiles,
            low_coverage_warning,
            max_intermediate_tiles,
            threads,
            files):
    """Subtype microbial genomes using SNV targeting k-mer subtyping schemes.

    Includes subtyping schemes for:

    - Salmonella enterica spp. enterica serovar Heidelberg

    - Salmonella enterica spp. enterica serovar Enteritidis

    Developed by Geneviève Labbé, James Robertson, Peter Kruczkiewicz, Marisa Rankin, Matthew Gopez, Chad R. Laing, Philip Mabon, Kim Ziebell, Aleisha R. Reimer, Lorelee Tschetter, Gary Van Domselaar, Sadjia Bekal, Kimberley A. MacDonald, Linda Hoang, Linda Chui, Danielle Daignault, Durda Slavic, Frank Pollari, E. Jane Parmley, Philip Mabon, Elissa Giang, Lok Kan Lee, Jonathan Moffat, Marisa Rankin, Joanne MacKinnon, Roger Johnson, John H.E. Nash.
    """
    does_file_exist(output_simple_summary_path, force)
    does_file_exist(output_summary_path, force)
    does_file_exist(output_tile_results, force)
    scheme_fasta = get_scheme_fasta(scheme)
    scheme_subtype_counts = subtype_counts(scheme_fasta)

    subtyping_params = init_subtyping_params(**locals())
    input_contigs, input_reads = collect_inputs(**locals())
    if len(input_contigs) == 0 and len(input_reads) == 0:
        no_files_exception = click.UsageError('No input files specified!')
        click.secho('Please see -h/--help for more info', err=True)
        raise no_files_exception
    df_md = None
    if scheme_metadata:
        df_md = read_metadata_table(scheme_metadata)

    subtype_results = []  # type: List[Tuple[Subtype, pd.DataFrame]]
    if len(input_contigs) > 0:
        contigs_results = subtype_contigs_samples(input_genomes=input_contigs,
                                                  scheme=scheme,
                                                  scheme_name=scheme_name,
                                                  subtyping_params=subtyping_params,
                                                  scheme_subtype_counts=scheme_subtype_counts,
                                                  n_threads=threads)
        logging.info('Generated %s subtyping results from %s contigs samples', len(contigs_results), len(input_contigs))
        subtype_results += contigs_results
    if len(input_reads) > 0:
        reads_results = subtype_reads_samples(reads=input_reads,
                                              scheme=scheme,
                                              scheme_name=scheme_name,
                                              subtyping_params=subtyping_params,
                                              scheme_subtype_counts=scheme_subtype_counts,
                                              n_threads=threads)
        logging.info('Generated %s subtyping results from %s contigs samples', len(reads_results), len(input_reads))
        subtype_results += reads_results

    dfs = [df for st, df in subtype_results]  # type: List[pd.DataFrame]
    dfsummary = pd.DataFrame([attr.asdict(st) for st, df in subtype_results])
    dfsummary = dfsummary[SUBTYPE_SUMMARY_COLS]

    if dfsummary['avg_tile_coverage'].isnull().all():
        dfsummary = dfsummary.drop(labels='avg_tile_coverage', axis=1)

    if df_md is not None:
        dfsummary = merge_metadata_with_summary_results(dfsummary, df_md)

    kwargs_for_pd_to_table = dict(sep='\t', index=None, float_format='%.3f')
    kwargs_for_pd_to_json = dict(orient='records')

    if output_summary_path:
        dfsummary.to_csv(output_summary_path, **kwargs_for_pd_to_table)
        if json_output:
            dfsummary.to_json(JSON_EXT_TMPL.format(output_summary_path), **kwargs_for_pd_to_json)
        logging.info('Wrote subtyping output summary to %s', output_summary_path)
    else:
        # if no output path specified for the summary results, then print to stdout
        print(dfsummary.to_csv(sep='\t', index=None))

    if output_tile_results:
        if len(dfs) > 0:
            dfall = pd.concat(dfs)  # type: pd.DataFrame
            dfall.to_csv(output_tile_results, **kwargs_for_pd_to_table)
            logging.info('Tile results written to "{}".'.format(output_tile_results))
            if json_output:
                dfall.to_json(JSON_EXT_TMPL.format(output_tile_results), **kwargs_for_pd_to_json)
                logging.info(
                    'Tile results written to "{}" in JSON format.'.format(JSON_EXT_TMPL.format(output_tile_results)))
        else:
            logging.error(
                'No tile results generated. No tile results file written to "{}".'.format(output_tile_results))

    if output_simple_summary_path:
        if 'avg_tile_coverage' in dfsummary.columns:
            df_simple_summary = dfsummary[['sample', 'subtype', 'avg_tile_coverage', 'qc_status', 'qc_message']]
        else:
            df_simple_summary = dfsummary[['sample', 'subtype', 'qc_status', 'qc_message']]

        if df_md is not None:
            df_simple_summary = merge_metadata_with_summary_results(df_simple_summary, df_md)

        df_simple_summary.to_csv(output_simple_summary_path, **kwargs_for_pd_to_table)
        if json_output:
            df_simple_summary.to_json(JSON_EXT_TMPL.format(output_simple_summary_path), **kwargs_for_pd_to_json)


def parse_comma_delimited_floats(ctx: click.Context, param: click.Option, value: Optional[str]) -> Optional[
    List[float]]:
    if value is None:
        return value

    if ',' in value:
        # TODO: more validation of user input values?
        return [float(x) for x in value.split(',')]
    else:
        return [float(value)]


@cli.command()
@click.option('-v','--vcf-file-path',
              required=True,
              type=click.Path(exists=True, dir_okay=False),
              help='Variant calling file (VCF) of a collection of input genomes for population of interest against a '
                   'reference genome that must be specified with --reference-genome-path')
@click.option('-r','--reference-genome-path',
              required=True,
              type=click.Path(exists=True, dir_okay=False),
              help='Reference genome assembly file path. The reference used in the creation of the input VCF file.')
@click.option('--phylo-tree-path',
              required=False,
              type=click.Path(exists=True, dir_okay=False),
              help='Optional phylogenetic tree created from variant calling analysis.')
@click.option('-d','--distance-thresholds',
              required=False,
              type=str,
              callback=parse_comma_delimited_floats,
              help='Comma delimited list of distance thresholds for creating hierarchical clustering groups '
                   '(e.g. "0,0.05,0.1,0.15")')
@click.option('-o','--output-folder-path',
                required=True,
                type=click.Path(exists=True, dir_okay=False),
                help='Output folder name in which schema file would be located'
                )
@click.option('-s', '--schema-name',
                required=False,
                type=str,
                help='A unique name for the schema file that is generated, the default is just'
                '{bio_hansel-schema-reference_genome_name}-{schema_version}' )
@click.option('-m', '--schema-version',
                required=False,
                type=str,
                help='An optional version number for the schema file that is generated' )
@click.option('-u','--maximum-threshold',
                required=True,
                type=float,
                help='Maximum threshold to be tested using the hierarchical clustering scheme'
                )
@click.option('-t','--minimum-threshold',
                type=float,
                required=True,
                help='Minimum threshold to be tested using the hierarchical clustering scheme'
                )
@click.option('-p','--padding-sequence-length',
                required=True,
                type=int,
                help='Output folder name in which schema file would be located'
                )
@click.option('-f','--reference-genome-format',
                required=True,
                type=str,
                help='Reference genome file format, i.e. fasta, genbank'
                )


def create(vcf_file_path, reference_genome_path, phylo_tree_path, distance_thresholds, maximum_threshold, minimum_threshold):
    """Create a biohansel subtyping scheme.

    From the results of a variant calling analysis, create a biohansel subtyping with single nucleotide variants (SNV)
    that discriminate subpopulations of genomes from all other genomes.
    """
    click.secho(f'VCF file path: {vcf_file_path}', fg='green')
    click.secho(f'Reference genome file path: {reference_genome_path}', fg='red')
    click.secho(f'Phylogenetic tree file path: {phylo_tree_path}', fg='yellow')
    click.secho(f'Distance thresholds: {distance_thresholds}', fg='blue')
    logging.info(f'Creating biohansel subtyping scheme from SNVs in "{vcf_file_path}" using reference genome '
                 f'"{reference_genome_path}" at {distance_thresholds if distance_thresholds else "all possible"} '
                 f'distance threshold levels.')
    
    if minimum_threshold >= maximum_threshold:
        threshold_exception=click.UsageError('maximum_threshold has to be bigger than minimum_threshold ')
        logging.error("max_threshold has to be bigger than min_threshold")


