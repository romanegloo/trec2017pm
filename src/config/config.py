import os

base_dir = base_dir = '/home/jiho/research/trec2017/'
PATHS = {
    'logfile': os.path.join(base_dir, 'var/runner.log'),
    'xsl-medline': os.path.join(base_dir, 'src/config/medline.xsl'),
    'xsl-trial': os.path.join(base_dir, 'src/config/trials.xsl'),
    'data-medline': os.path.join(base_dir, 'data/articles'),
    'data-trials': os.path.join(base_dir, 'data/clinicaltrials'),
}
CONF_TWILIO = {
    'num_from': "16693337891",
    'num_to': "18123457891",
    'account_sid': 'AC339ad853d7e4105465ff50d3d5be03eb',
    'auth_token': '81b060bae2907aa16c7d8ff92cbca48e'
}