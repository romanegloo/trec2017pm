import os
import sys
import lxml.etree as et
import re
import requests
import json
import pprint

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config as cfg
import Trec2017pm.logger as logger
import Trec2017pm.utils as utils

logger = logger.Logger()  # singleton
pp = pprint.PrettyPrinter(indent=4)


def run_import_docs():
    """
    Given the xslt file, the medline files will be transformed and used to 
    update the existing record or create new record in the Solr core (articles)

    note that the default JVM-memory size of solr is 500Mb which is not
    enough for importing medline docs. Increase it to 4g as below:
    "./solr restart -m 4g"
    """
    import gzip

    # - read xsl file
    if not os.path.isfile(cfg.PATHS['xsl-article']):
        logger.log('ERROR', 'xsl-article [{}] cannot be found'.
                   format(cfg.PATHS['xsl-article']), die=True, printout=True)
    else:
        logger.log('DEBUG', 'reading xsl file for medline xml files')

    try:
        xslt = et.parse(cfg.PATHS['xsl-article'])
        transformer = et.XSLT(xslt)
    except:
        e = sys.exc_info()[0]
        logger.log('ERROR', 'xsl parsing error: {}'.format(e), printout=True)

    # read all doc source files (*.gz) in part[1..5] directories
    # (total num of files must be 888)
    doc_files = []
    for root, dirs, files in os.walk(cfg.PATHS['data-articles']):
        if not re.match(r"part[1-5]", root.split(os.sep)[-1]):
            continue
        for file in files:
            if not file.endswith('gz'):
                continue
            doc_files.append(os.path.join(root, file))
    logger.log('INFO', '{} medline documents found from {}'. \
               format(len(doc_files), cfg.PATHS['data-articles']))

    # for debugging
    # doc_files.append(
    #     '/home/jiho/research/trec2017/data/articles/doc_sample-long.xml')

    # if skip_files is given, read the list
    skip_files = []
    if cfg.skip_files and os.path.exists(cfg.skip_files):
        with open(cfg.skip_files) as f:
            skip_files = f.read().splitlines()
        skip_fh = open(cfg.skip_files, 'a', buffering=1)

    for i, file in enumerate(doc_files):
        attempts = 3
        if file in skip_files:
            logger.log('WARNING',
                       'file already imported. skipping... {}'.format(file),
                       printout=True)
            sys.stdout.flush()
            continue
        logger.log('INFO', 'parsing a doc file {}'.format(file))

        # - convert to a solr update xml format
        _, ext = os.path.splitext(file)
        if ext == 'gz':
            doc_trans = transformer(et.parse(gzip.open(file)))
        else:
            doc_trans = transformer(et.parse(file))

        # pre-process using metamap [CUI]
        # doc_trans = utils.extract_cuis(doc_trans)

        # - run update with the converted file
        url = "http://localhost:8983/solr/articles/update?commit=true"
        headers = {'content-type': 'text/xml; charset=utf-8'}
        while attempts > 0:
            r = None
            try:
                r = requests.post(url, data=et.tostring(doc_trans),
                                  headers=headers)
            except requests.exceptions.RequestException as e:
                logger.log('ERROR', 'request exception: {}'.format(e),
                           die=True, printout=True)

            if r.status_code != 200:
                attempts -= 1
                logger.log('ERROR', 'requests error:')
                logger.log('ERROR', r.text)
                r.raise_for_status()
                if attempts < 0:
                    logger.log('CRITICAL', 'terminating', die=True,
                               printout=True)
            else:
                # - log the results
                logger.log('INFO', 'importing doc files in progress {}/{}'.
                           format(i+1, len(doc_files)), printout=True)
                if cfg.skip_files:
                    skip_fh.write(file + '\n')

                if cfg.sms and (i+1) % 100 == 0:
                    logger.sms('importing doc files {}/{}'. \
                               format(i+1, len(doc_files)))

                break
    logger.log('INFO', 'importing medline documents completed', printout=True)

    # added for importing extra AACR documents
    doc_files_extra = []
    path_extra = os.path.join(cfg.PATHS['data-articles'], 'extra_abstracts')
    for root, dirs, files in os.walk(path_extra):
        for file in files:
            if not file.startswith('AACR') or not file.endswith('txt'):
                continue
            doc_files_extra.append(os.path.join(root, file))

    logger.log('INFO', '{} AACR documents found from {}'. \
               format(len(doc_files_extra), path_extra), printout=True)


    # creating document xml in solr add format
    et_add = et.Element('add')
    attempts = 3
    for i, file in enumerate(doc_files_extra):
        if file in skip_files:
            logger.log('WARNING',
                       'file already imported. skipping... {}'.format(file),
                       printout=True)
            sys.stdout.flush()
            continue
        with open(file) as f:
            doc_lines = f.read().splitlines()

        logger.log('INFO', 'parsing a doc file {}'.format(file), printout=True)
        et_doc = et.Element('doc')
        # use the filename as an id
        id, _ = os.path.splitext(os.path.basename(file))
        et_id = et.Element('field', name='id')
        et_id.text = id
        et_doc.append(et_id)

        # journal-title
        title = re.sub(r'^Meeting: ', '', doc_lines[0])
        if len(title) > 0:
            et_title = et.Element('field', name='journal-title')
            et_title.text = title
            et_doc.append(et_title)

        # subject
        subject = re.sub(r'^Title: ', '', doc_lines[1])
        if len(subject) > 0:
            et_subj = et.Element('field', name='subject')
            et_subj.text = subject
            et_doc.append(et_subj)

        # abstract
        abstract = ''.join(doc_lines[4:])
        if len(abstract) > 0:
            et_abs = et.Element('field', name='abstract')
            et_abs.text = abstract
            et_doc.append(et_abs)
        et_add.append(et_doc)

    # - run update with the converted file
    url = "http://localhost:8983/solr/articles/update?commit=true"
    headers = {'content-type': 'text/xml; charset=utf-8'}
    while attempts > 0:
        r = None
        try:
            r = requests.post(url, data=et.tostring(et_add),
                              headers=headers)
        except requests.exceptions.RequestException as e:
            logger.log('ERROR', 'request exception: {}'.format(e),
                       die=True, printout=True)

        if r.status_code != 200:
            attempts -= 1
            logger.log('ERROR', 'requests error:')
            logger.log('ERROR', r.text)
            r.raise_for_status()
            if attempts < 0:
                logger.log('CRITICAL', 'terminating', die=True,
                           printout=True)
        else:
            # - log the results
            logger.log('INFO', 'importing doc files in progress {}/{}'.
                       format(i+1, len(doc_files_extra)), printout=True)
            if cfg.skip_files:
                skip_fh.write(file + '\n')

            if cfg.sms and (i+1) % 1000 == 0:
                logger.sms('importing doc files {}/{}'. \
                           format(i+1, len(doc_files_extra)))

            break


def run_import_trials():
    """
    Given corresponding xslt file, the trials xml files are transformed and 
    used to update the existing record or create new record in the Solr core 
    (trials)
    """

    batch = 500
    url = "http://localhost:8983/solr/trials/update?commit=true"

    # - read xsl file
    if not os.path.isfile(cfg.PATHS['xsl-trial']):
        logger.log('ERROR', 'xsl-trial [{}] cannot be found'.
                   format(cfg.PATHS['xsl-trial']), die=True, printout=True)
    else:
        logger.log('DEBUG', 'reading xsl file for clinical trials xml files')

    try:
        xslt = et.parse(cfg.PATHS['xsl-trial'])
        transformer = et.XSLT(xslt)
    except:
        e = sys.exc_info()[0]
        logger.log('ERROR', 'xsl parsing error: {}'.format(e), printout=True)

    # read all trial source files (*.xml) in trial data sub-directories
    # (total num of files must be 241006)
    trial_files = []
    for root, dirs, files in os.walk(cfg.PATHS['data-trials']):
        if not re.match(r"\d+", root.split(os.sep)[-1]):
            continue
        for file in files:
            if not file.endswith('xml'):
                continue
            trial_files.append(os.path.join(root, file))
    logger.log('INFO', '{} trials found from {}'. \
               format(len(trial_files), cfg.PATHS['data-trials']))

    # if skip_files is given, read the list
    skip_files = []
    if cfg.skip_files and os.path.isfile(cfg.skip_files):
        with open(cfg.skip_files) as f:
            skip_files = f.read().splitlines()
        skip_fh = open(cfg.skip_files, 'a', buffering=1)

    docs_collated = 0
    skipped_files = 0
    completed_files = 0
    for i, file in enumerate(trial_files):
        attempts = 3
        if file in skip_files:
            skipped_files += 1
            if skipped_files % 1000 == 0:
                logger.log('INFO', 'skipping files [{}/{}]'. \
                           format(skipped_files, len(skip_files)))
            continue
        logger.log('INFO', 'parsing a trial file {}'.format(file))

        if docs_collated == 0:
            req = et.Element('add')

        # - transform trial xml to solr update format
        trial_trans = transformer(et.parse(file))
        # - pre-indexing nlp process
        utils.age_normalize(trial_trans)
        if docs_collated < batch:
            req.append(trial_trans.getroot())
            docs_collated += 1

        # - run update, if docs_collated reached batch or end of files
        if docs_collated == batch or i == len(trial_files)-1:
            docs_collated = 0
            headers = {'content-type': 'text/xml; charset=utf-8'}

            while attempts > 0:
                try:
                    r = requests.post(url, data=et.tostring(req),
                                     headers=headers)
                except requests.exceptions.RequestException as e:
                    logger.log('ERROR', 'request exception: {}'.format(e))
                    logger.log('ERROR', r, die=True, printout=True)

                if r.status_code != 200:
                    attempts -= 1
                    logger.log('ERROR', r.text)
                    logger.log('ERROR', 'data: \n' + str(et.tostring(req)))
                    r.raise_for_status()
                    if attempts < 0:
                        logger.log('CRITICAL', 'terminating', die=True,
                                   printout=True)
                else:
                    completed_files += 1
                    # - log the results
                    logger.log('INFO',
                               'importing trial files in progress {}/{}'. \
                               format(i+1, len(trial_files)), printout=True)
                    if cfg.skip_files:
                        skip_fh.write(file + '\n')

                    if cfg.sms and completed_files % 5000 == 0:
                        logger.sms('importing trial files {}/{}'. \
                                   format(i+1, len(trial_files)))
                    break
    logger.log('INFO', 'importing trials completed', printout=True)


def run_queries(queries, res_path, target):
    assert target in ['a', 't', 'b'], "target source is undefined"
    top_docs_a = os.path.join(res_path, 'top_articles.out')
    top_docs_t = os.path.join(res_path, 'top_trials.out')

    if target in ['a', 'b']:
        with open(top_docs_a, 'w') as top_docs:
            for i, query in enumerate(queries):
                # if cfg.topic and i+1 != int(cfg.topic):
                #     print('skipping', i, cfg.topic)
                #     continue

                print("querying topic #{} on articles".format(i+1))
                sys.stdout.flush()
                ranked_docs = []
                res = _query(query, target='a')
                for rank, doc in enumerate(res['response']['docs']):
                    ranked_docs.append(doc['id'])
                    # write ranked list for trec_eval
                    topic = int(cfg.topic) if cfg.topic else i+1
                    top_docs.write("{} Q0 {} {} {} run_name\n".
                                   format(topic, doc['id'], rank, doc['score']))
                # save query per topic
                qfile = os.path.join(res_path, 'a{}.query'.format(i+1))
                with open(qfile, 'w') as qf:
                    qf.write(query['query'] + "\n")
        logger.log('INFO', "result file [{}] saved".format(top_docs_a),
                   printout=True)
    if target in ['t', 'b']:
        with open(top_docs_t, 'w') as top_docs:
            for i, query in enumerate(queries):
                # if cfg.topic and i+1 != int(cfg.topic):
                #     continue

                ranked_docs = []
                print("querying topic #{} on trials".format(i+1))
                res = _query(query, target='t')
                for rank, doc in enumerate(res['response']['docs']):
                    ranked_docs.append(doc['id'])
                    # write ranked list for trec_eval
                    topic = int(cfg.topic) if cfg.topic else i+1
                    top_docs.write("{} Q0 {} {} {} run_name\n".
                                   format(topic, doc['id'], rank, doc['score']))
                    if rank < 10:
                        top_docs.write("official_title: {}"
                                       "".format(doc['official_title']))
                # save query per topic
                qfile = os.path.join(res_path, 't{}.query'.format(i+1))
                with open(qfile, 'w') as qf:
                    qf.write(query['query'] + "\n")
        logger.log('INFO', "result file [{}] saved".format(top_docs_t),
                   printout=True)


def _query(t, target):
    if target == 'a':
        url = "http://localhost:8983/solr/articles/query?"
    elif target == 't':
        url = "http://localhost:8983/solr/trials/query?"

    if 'fl' in cfg.CONF_SOLR:
        url += 'fl=' + cfg.CONF_SOLR['fl'] + '&'
    if 'rows' in cfg.CONF_SOLR:
        url += 'rows=' + str(cfg.CONF_SOLR['rows']) + '&'
    headers = {
        'content-type': 'application/json',
        'Accept-Charset': 'UTF-8'}
    try:
        r = requests.post(url, data=json.dumps(t), headers=headers)
    except requests.exceptions.RequestException as e:
        logger.log('ERROR', 'request exception: {}'.format(e))
        logger.log('ERROR', r, die=True, printout=True)

    if r.status_code != 200:
        logger.log('ERROR', t, printout=True)
    else:
        logger.log('INFO', 'query processed: {}'.format(t))
        res = json.loads(r.text)
        # pp.pprint(res)
        return res

