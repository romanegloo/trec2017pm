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
from nltk.corpus import stopwords
import re
import itertools
from copy import deepcopy

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config as cfg
from Trec2017pm import logger, solr, utils
from umls_api import UMLS_api
import random


stopwords = stopwords.words('english')
extra_stopwords = ['gene']

def update_obj(dst, src):
    """helper function in order to use 'config' namespace as global 
    parameters among module screipts"""
    for key, value in src.items():
        setattr(dst, key, value)


def _run_exp_1():
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)
    top_docs = os.path.join(resdir, 'top_articles.out')
    eval_res = os.path.join(resdir, 'eval_articles.out')

    # topics
    topics = utils.parse_topics(cfg.PATHS['topics'], qexp_atoms=True)  # read

    with open(top_docs, 'w') as toptrec:
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


def _run_exp_7():
    """disease name in meshheading"""
    target = 't'
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    # parse topics
    queries = utils.parse_topics(cfg.PATHS['topics'], target)

    # run queries
    solr.run_queries(queries, resdir, target=target)

    # run evaluators
    if cfg.evaluate:
        utils.run_evaluators(resdir)


def _run_exp_optimize_weights():
    """ ! do not delete this run
    we have 5 query clauses; disease, gene, variant, demographics, others
    We want to randomly select weights for each, while maintaining the
    priorities of the groups, such that
        mesh:disease, mesh:gene
            > disease, gene, mutation
            > mesh:other
            > other
            > mesh:demographic
    for now, as an intermediate step, the order is as below:
        disease
            > gene
            > mutation
            > mesh:demographic
    """
    target = 'a'
    tmpl_dir = 'var/res-weight_template_2'
    run = 10
    count_update = 0
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    top_k = 10
    # prev_weight = random.sample(range(0, 300), 7)
    prev_weight = [85.93260050245044, 19.67701749578877, 101.07024160705741,
                   182.842193953625, 262.2910718694024, 210.19718837058338,
                   398.7569042508689]
    curr_weight = deepcopy(prev_weight)
    variation = 5
    best_score = 0

    for i in range(run):
        logger.log('INFO', 'opt running - #{}'.format(i+1), printout=True)
        if i == 0:
            pass
        elif i % 10 == 1:  # occasionally generate totally random weights
            curr_weight = random.sample(range(0, 300), 7)
        elif i % 10 == 2:  # larger variation
            curr_weight = [max(0, random.gauss(wt, variation * 10))
                           for wt in prev_weight]
        elif i % 5 == 3:  # just change one weight
            curr_weight = deepcopy(prev_weight)
            idx = random.randint(0, len(curr_weight)-1)
            curr_weight[idx] = random.gauss(curr_weight[idx], variation)
        else:
            # randomize curr_weight
            curr_weight = [max(0, random.gauss(wt, variation))
                           for wt in prev_weight]
        queries = []
        for i in range(1, 31):
            file = os.path.join(tmpl_dir, 'a{}.template'.format(i))
            with open(file) as f:
                q = f.read()
            for j in range(7):
                q = q.replace('<WT{}>'.format(j+1),
                              str(round(curr_weight[j]/100, 2)))
            queries.append({'query': q})
        # run queries
        solr.run_queries(queries, resdir, target=target)

        print("previous weight: ", prev_weight)
        print("random weight: ", curr_weight)
        # run evaluators
        if cfg.evaluate:
            infAP, infNDCG = utils.run_evaluators(resdir)
            score = 2 / ((1 / infAP) + (1 / infNDCG))
            if best_score < score:
                count_update += 1
                logger.log('INFO', 'updating weights', printout=True)
                # update best_score and prev_weight
                prev_weight = curr_weight
                best_score = score
    logger.log('INFO', "Optimization finished:", printout=True)
    logger.log('INFO',
               "{} times out of {} runs updated"
               "".format(count_update, run), printout=True)
    logger.log('INFO',
               "best_weights: {}"
               "".format(', '.join([str(x) for x in prev_weight])),
               printout=True)
    logger.log('INFO', "best_score: {}".format(best_score), printout=True)

    # for i in range(run):
    #     # weights = sorted(random.sample(range(0, 300), 4))
    #     # weights = weights[::-1]  # reversed
    #     weights = random.sample(range(0, 300), 4)
    #     str_weights = ', '.join([str(x/100) for x in weights])
    #     logger.log('INFO', 'random weights: ' + str_weights, printout=True)
    #
    #     # read from template queries
    #     queries = []
    #     for i in range(1, 31):
    #         file = os.path.join(tmpl_dir, 'a{}.template'.format(i))
    #         with open(file) as f:
    #             q = f.read()
    #         q = q.replace('<WT1>', str(weights[0]/100))
    #         q = q.replace('<WT2>', str(weights[1]/100))
    #         q = q.replace('<WT3>', str(weights[2]/100))
    #         q = q.replace('<WT4>', str(weights[3]/100))
    #         queries.append({'query': q})
    #     # run queries
    #     solr.run_queries(queries, resdir, target=target)
    #
    #     # run evaluators
    #     if cfg.evaluate:
    #         infAP, infNDCG = utils.run_evaluators(resdir)
    #         score = 2 / ((1 / infAP) + (1 / infNDCG))
    #         insert_at = top_k
    #         for i in reversed(range(top_k)):
    #             if best_scores[i] < score and i >= 0:
    #                 insert_at = i
    #                 continue
    #         best_scores.insert(insert_at, score)
    #         best_scores = best_scores[:top_k]
    #         best_weights.insert(insert_at, weights)
    #         best_weights = best_weights[:top_k]
    #
    # print(best_weights, best_scores)


if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="run different tasks",
                        choices=['import_docs', 'import_trials', 'experiment'])
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
    elif args.command == 'experiment':
        # _run_exp_optimize_weights()
        _run_exp_7()

