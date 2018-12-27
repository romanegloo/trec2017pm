import os
import socket

hostname = socket.gethostname()
if hostname == '***':
    base_dir = '/***/***'
elif hostname == '***':
    base_dir = '/***/***'
else:
    base_dir = '/***/***'

PATHS = {
    'vardir': os.path.join(base_dir, 'var'),
    'logfile': os.path.join(base_dir, 'var/runner.log'),
    'xsl-article': os.path.join(base_dir, 'src/config/articles.xsl'),
    'xsl-trial': os.path.join(base_dir, 'src/config/trials.xsl'),
    'data-articles': os.path.join(base_dir, 'data/articles'),
    'data-trials': os.path.join(base_dir, 'data/clinicaltrials'),
    'topics': os.path.join(base_dir, 'data/topics2017.xml'),
    'cache': os.path.join(base_dir, 'data/cache'),
    'extra-topics': os.path.join(base_dir, 'data/extra_topics.xml'),
    'trec_eval': os.path.join(base_dir, 'src/trec_eval'),
    'sample_eval': os.path.join(base_dir, 'src/sample_eval.pl'),
    'rel_file': os.path.join(base_dir, 'data/cosmic_ref/rel_file.cosmic'),
    'rel_file_s': os.path.join(base_dir, 'data/cosmic_ref/rel_file_s.cosmic'),
}
CONF_SOLR = {
    'rows': 1000,  # number of returned rows
    'fl': '*,score',
    'umls_qe': ['disease', 'gene'],  # add query expansion on the fields
    'enable_conj_uprank': True,
    'qe_umls': True,
    'qe_MoD': True,
    'wt_disease': 0.2394,       # wt1
    'wt_meshDisease': 0.1330,   # wt2
    'wt_gene': 2.8416,          # wt3
    'wt_meshGene': 0.0116,      # wt4
    'wt_mutation': 1.5502,      # wt5
    'wt_meshMutation': 0.3702,  # wt6
    'wt_meshDemo': 2.7745,      # wt7
    'wt_conjunctive': 2.2786,   # wt8
    'wt_other': 0.01,   # not using on articles yet
    'wt_disease_c': 0.86,
    'wt_meshDisease_c': 0.20,
    'wt_gene_c': 1.01,
    'wt_meshGene_c': 1.83,
    'wt_mutation_c': 2.63,
    'wt_meshMutation_c': 2.10,
    'wt_meshDemo_c': 3.99,
    'wt_other_c': 0.01,   # not using on articles yet
    'wt_multiplier': '^',
}

CONF_MM = {
    'restrict_to_sts': [
        'aapp',  # T116|Amino Acid, Peptide, or Protein|
        'aggp',  # T100|Age Group
        'comd',  # T049|Cell or Molecular Dysfunction
        'dsyn',  # T047|disease
        'genf',  # T045|Genetic Fun ction
        'gngm',  # T028|Gene or Genome
        'neop',  # T191|Neoplastic Process
        'nnon',  # T114|Nucleic Acid, Nucleoside, or Nucleotide
    ],
    'silent': True
}
CONF_UMLS = {
    'api_key': '****',
}
CONF_MUT_TYPES = {
    'amplification': ["Gene Amplification"],
    'fusion': ["Gene Fusion"],
    'inactivating': ["Gene Silencing"],
    'loss': ["Gene Deletion"],
    'deletion': ["Gene Deletion"],
    'transcription': ["Transcription, Genetic"]
}
