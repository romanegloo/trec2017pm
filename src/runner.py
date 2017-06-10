#!/usr/bin/env python3

"""
this script is for running all tasks with the given user commands.
- importing data sources to Solr server in two cores (medline, trials)
- run queries with a patient topic
- run evaluation
- run experiments
"""
from __future__ import print_function

import os
import sys
import argparse
from time import gmtime, strftime
import subprocess

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config as cfg
from Trec2017pm import logger, solr, utils


def update_obj(dst, src):
    """helper function in order to use 'config' namespace as global 
    parameters among module screipts"""
    for key, value in src.items():
        setattr(dst, key, value)

def _run_exp_1():
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)
    top_trec = os.path.join(resdir, 'top_trec.res')
    evalfile = os.path.join(resdir, 'eval.out')

    topics = utils.parse_topics(cfg.PATHS['topics'], qexp_atoms=True)  # read
    # topics

    with open(top_trec, 'w') as toptrec:
        for i, topic in enumerate(topics):
            if cfg.topic and i+1 != int(cfg.topic):
                continue
            print("\ntopic #{}".format(i+1))
            tfile = os.path.join(resdir, 't{}.res'.format(i+1))

            ranked_docs = []
            with open(tfile, 'w') as tfile_out:
                res = solr.query(topic)
                for rank, doc in enumerate(res['response']['docs']):
                    ranked_docs.append(doc['id'])
                    # store the search results in a file in the trec_eval format
                    # [qid] [dummy] [rank] [score] [run_name]
                    tfile_out.write("{} Q0 {} {} {} run_name\n".
                                    format(i+1, doc['id'], rank, doc['score']))
                    # write ranked list for trec_eval
                    toptrec.write("{} Q0 {} {} {} run_name\n".
                                  format(i+1, doc['id'], rank, doc['score']))
            print("result file [{}] written".format(tfile))

    if cfg.evaluate:
        # run trec_eval
        output = subprocess.check_output(
            [cfg.PATHS['trec_eval'], '-q', cfg.PATHS['rel_file'], top_trec])
        with open(evalfile, 'a') as eval:
            eval.write(output.decode('ascii'))

        # run sample_eval
        output = subprocess.check_output(
            [cfg.PATHS['sample_eval'], '-q', cfg.PATHS['rel_file_s'], top_trec])
        with open(evalfile, 'a') as eval:
            eval.write(output.decode('ascii'))
            logger.log('INFO',
                       'evaluation output saved [{}]'.format(evalfile),
                       printout=True)



if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="run different tasks",
                        choices=['import_docs', 'import_trials', 'exp'])
    parser.add_argument("-s", "--sms", action="store_true",
                        help="send sms notification with progress status")
    parser.add_argument("--skip_files", help="skip files already imported")
    parser.add_argument("-e", "--evaluate", action="store_true",
                        help="evaluate wrt. cosmic pubmed ref list")
    parser.add_argument("-t", "--topic", help="specify topic to query")
    args = parser.parse_args()
    update_obj(cfg, vars(args))

    # initialize logger, solr
    logger = logger.Logger()
    logger.log('INFO', '-'*80 + '\ncommand requested: ' + cfg.command,
               printout=True)

    if args.command == 'import_docs':
        solr.run_import_docs()
    elif args.command == 'import_trials':
        solr.run_import_trials()
    elif args.command == 'exp':
        _run_exp_1()
