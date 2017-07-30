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
from collections import OrderedDict


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


def _run_exp_10():
    """disease name in meshheading"""
    target = 'a'
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    # parse topics
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], 'a')
    # queries_trials = utils.parse_topics(cfg.PATHS['topics'], 't')

    # run queries
    solr.run_queries(queries_articles, resdir, target='a')
    # solr.run_queries(queries_trials, resdir, target='t')

    utils.run_evaluators(resdir)


def _run_exp_11():
    """up-rank conjunctive results"""
    target = 't'
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    # run default quries
    cfg.CONF_SOLR['enable_conj_uprank'] = False
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], target)
    solr.run_queries(queries_articles, resdir, target=target)

    # run conjunctive
    cfg.CONF_SOLR['enable_conj_uprank'] = True
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], target)
    solr.run_queries(queries_articles, resdir, target=target)

    # merge two ranked lists: up-ranked the one of conjunctive
    merge_ranked_list(resdir)

    # run evaluators
    if cfg.evaluate and target == 'a':
        utils.run_evaluators(resdir)


def _run_exp_trial():
    """temporary run for trials result"""
    target = 't'
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    cfg.CONF_SOLR['enable_conj_uprank'] = False
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], target)
    solr.run_queries(queries_articles, resdir, target=target)

    # run conjunctive
    cfg.CONF_SOLR['enable_conj_uprank'] = True
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], target)
    solr.run_queries(queries_articles, resdir, target=target)

    # merge two ranked lists: up-ranked the one of conjunctive
    merge_ranked_list(resdir, target=target)

    # run evaluators
    if cfg.evaluate and target == 'a':
        utils.run_evaluators(resdir)


def _run_exp_13():
    """use manually crafted quries"""
    target = 'a'
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-exp13-manual')

    # run normal queries
    queries_articles = []
    for i in range(1, 31):
        if cfg.topic and i != int(cfg.topic):
            continue
        q_file = os.path.join(resdir, "a{}.query".format(i))
        if not os.path.exists(q_file):
            logger.log('ERROR', "query #{} does not exist".format(i),
                       printout=True)
            return
        with open(q_file) as fin:
            queries_articles.append({'query': fin.read()})
    solr.run_queries(queries_articles, resdir, target='a', save_queries=False)

    # run cjt queries
    cfg.CONF_SOLR['enable_conj_uprank'] = True
    queries_articles = []
    q_no = []
    for i in range(1, 31):
        if cfg.topic and i != int(cfg.topic):
            continue
        q_file = os.path.join(resdir, "a{}-cjt.query".format(i))
        if not os.path.exists(q_file):
            continue
        else:
            q_no.append(i)
        with open(q_file) as fin:
            queries_articles.append({'query': fin.read()})
    solr.run_queries(queries_articles, resdir, target='a',
                     q_no=q_no, save_queries=False)

    # merge two ranked lists: up-ranked the one of conjunctive
    merge_ranked_list(resdir)

    # run evaluators
    if cfg.evaluate and target == 'a':
        utils.run_evaluators(resdir)


def _run_exp_14():
    """exp11 + exp12"""
    target = 'a'
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    # run default quries
    cfg.CONF_SOLR['enable_conj_uprank'] = False
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], 'a')
    solr.run_queries(queries_articles, resdir, target='a')

    # run conjunctive
    cfg.CONF_SOLR['enable_conj_uprank'] = True
    queries_articles = utils.parse_topics(cfg.PATHS['topics'], 'a')
    solr.run_queries(queries_articles, resdir, target='a')

    # merge two ranked lists: up-ranked the one of conjunctive
    merge_ranked_list(resdir)

    # run evaluators
    if cfg.evaluate and target == 'a':
        utils.run_evaluators(resdir)


def merge_ranked_list(resdir, target='a'):
    # read two top lists and overwrite with a new top_articles.out
    top_articles = os.path.join(resdir, 'top_articles.out')
    cjt_top_articles = os.path.join(resdir, 'top_articles-cjt.out')
    if target == 't':
        top_articles = os.path.join(resdir, 'top_trials.out')
        cjt_top_articles = os.path.join(resdir, 'top_trials-cjt.out')

    if not os.path.exists(top_articles) or not os.path.exists(cjt_top_articles):
        logger.log('ERROR', 'two ranked lists not found', printout=True)
        logger.log('ERROR', '{}\n{}'.format(top_articles, cjt_top_articles),
                   printout=True)
        return

    query_res = [dict() for _ in range(30)]
    top_scores = [0.] * 30
    """format:
    1 Q0 19737942 0 100.76604 run_name
    1 Q0 25121597 1 100.21548 run_name"""
    with open(top_articles) as f:
        for line in f:
            q_id, _, doc_id, pos, score, _ = line.split()
            q_id = int(q_id) - 1
            if top_scores[q_id] < float(score):
                top_scores[q_id] = float(score)
            query_res[q_id][doc_id] = float(score)
            # print("q_id:{} doc_id:{} score:{}".format(q_id, doc_id, score))

    # print([len(q) for q in query_res])
    # print(top_scores)
    with open(cjt_top_articles) as f_cjt:
        for line in f_cjt:
            q_id, _, doc_id, pos, score, _ = line.split()
            q_id = int(q_id) - 1
            query_res[q_id][doc_id] = float(score) + top_scores[q_id]

    # sort
    for i, q in enumerate(query_res):
        # print(i, len(q))
        res_od = OrderedDict(sorted(q.items(), key=lambda t: t[1],
                                    reverse=True))
        query_res[i] = res_od

    # write out
    orig_file = 'top_articles-orig.out' if target == 'a' else \
        'top_trials-orig.out'
    os.rename(top_articles, os.path.join(resdir, orig_file))
    with open(top_articles, 'w') as fout:
        for i, res in enumerate(query_res):
            q_id = i + 1
            pos = 0
            for k, v in res.items():
                if pos >= cfg.CONF_SOLR['rows']:
                    break
                fout.write("{} Q0 {} {} {:.6f} RUN2\n".format(q_id, k, pos, v))
                pos += 1


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
    tmpl_dir = 'var/q_tmpl-exp12'
    run = 100
    count_update = 0
    dt = strftime("%m%d%H%M%s", gmtime())  # datetime as an exp id
    resdir = os.path.join(cfg.PATHS['vardir'], 'res-'+dt)
    os.mkdir(resdir)

    top_k = 10
    # prev_weight = random.sample(range(0, 300), 7)
    # below is for exp11, do not remove
    prev_weight = [61.7131052045164, 139.5433048356918, 177.81197097303223,
                   92.7144638040653, 95.5334, 224.83844597239275,
                   583.6807943285283, 24.860191103787024]
    # below is for exp12
    prev_weight = [60.711201641273405, 4.880055149158676, 279.26698225881864,
                   10.125666977818522, 192.75185006506513, 76.04244782933952,
                   253.47416863967885, 212.58225480704252]
    prev_weight = [23.948835757798317, 13.309514268605971, 284.15669468723354,
                   1.1630530198432623, 155.01554494126165, 37.0197502834617,
                   277.45222362827445, 227.85804114860733]
    # [-2.2757592772051787, 4.164624621483287, 99.31682681787032, 171.97563793280884, 155.45324625453765, 75.8805921891793, 357.13763872425716, 297.9524237215415]

    curr_weight = deepcopy(prev_weight)
    variation = 5
    best_score = 0

    for i in range(run):
        logger.log('INFO', 'opt running - #{}'.format(i+1), printout=True)
        if i == 0:
            pass
        elif i % 10 == 1:  # occasionally generate totally random weights
            curr_weight = random.sample(range(0, 300), 8)
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
        q_no = [4, 8, 12, 16, 20, 24, 28]
        for i in range(1, 31):
            if i not in q_no:
                continue
            file = os.path.join(tmpl_dir, 'a{}.template'.format(i))
            with open(file) as f:
                q = f.read()
            for j in range(8):
                q = q.replace('<WT{}>'.format(j+1),
                              str(round(curr_weight[j]/100, 6)))
            queries.append({'query': q})
        # run queries
        solr.run_queries(queries, resdir, target=target, q_no=q_no)

        logger.log('INFO', "previous weight: {}".format(prev_weight),
                   printout=True)
        logger.log('INFO', "random weight: {}".format(curr_weight),
                   printout=True)
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

if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="run different tasks",
                        choices=['import_docs', 'import_trials',
                                 'import_extra', 'experiment'])
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
    elif args.command == 'import_extra':
        solr.run_import_extra()
    elif args.command == 'experiment':
        # _run_exp_optimize_weights()
        _run_exp_trial()
        # _run_exp_uprank()
        # _run_exp_11()
        # _run_exp_14()

