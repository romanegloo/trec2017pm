import os

base_dir = base_dir = '/home/jiho/research/trec2017/'
PATHS = {
    'vardir': os.path.join(base_dir, 'var'),
    'logfile': os.path.join(base_dir, 'var/runner.log'),
    'xsl-medline': os.path.join(base_dir, 'src/config/medline.xsl'),
    'xsl-trial': os.path.join(base_dir, 'src/config/trials.xsl'),
    'data-medline': os.path.join(base_dir, 'data/articles'),
    'data-trials': os.path.join(base_dir, 'data/clinicaltrials'),
    'topics': os.path.join(base_dir, 'data/topics2017.xml'),
    'extra-topics': os.path.join(base_dir, 'data/extra_topics.xml'),
    'trec_eval': os.path.join(base_dir, 'src/trec_eval'),
    'sample_eval': os.path.join(base_dir, 'src/sample_eval.pl'),
    'rel_file': os.path.join(base_dir, 'data/cosmic_ref/rel_file.cosmic'),
    'rel_file_s': os.path.join(base_dir, 'data/cosmic_ref/rel_file_s.cosmic'),
}
CONF_TWILIO = {
    'num_from': "16693337891",
    'num_to': "18123457891",
    'account_sid': 'AC339ad853d7e4105465ff50d3d5be03eb',
    'auth_token': '81b060bae2907aa16c7d8ff92cbca48e'
}
CONF_SOLR = {
    'rows': '500',  # number of returned rows
    'fl': '*,score'
}
CONF_MM = {
    'restrict_to_sts': [
        'aggp',  # T100|Age Group
        'comd',  # T049|Cell or Molecular Dysfunction
        'dsyn',  # T047|disease
        'genf',  # T045|Genetic Fun ction
        'gngm',  # T028|Gene or Genome
        'neop',  # T191|Neoplastic Process
        'nnon',  # T114|Nucleic Acid, Nucleoside, or Nucleotide
    ]
}
CONF_UMLS = {
    'api_key': '5cd21481-a538-4385-ad98-873b096397f5',
}