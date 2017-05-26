#!/usr/bin/env python3

"""
this script is for running all tasks with the given user commands.
- importing data sources to Solr server in two cores (medline, trials)
- run queries with a patient topic
- run evaluation
- run experiments
"""
from __future__ import print_function

import argparse
import logging
import os
import sys
import re
import requests
from twilio.rest import Client
import lxml.etree as et  # for xml transformation

base_dir = '/home/jiho/research/trec2017/'  # paths
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

def log(level, msg, die=False, printout=False):
    """
    logging wrapper
    """
    if level == 'DEBUG':
        logging.debug(msg)
    elif level == 'INFO':
        logging.info(msg)
    elif level == 'WARNING':
        logging.warning(msg)
    elif level == 'ERROR':
        logging.error(msg)
    elif level == 'CRITICAL':
        logging.critical(msg)

    if printout:
        print("[{}] {}".format(level, msg))
        sys.stdout.flush()

    if die:
        print("terminating... please read the log file for details")
        if args.sms:
            msg = twilio_cl.messages.create(
                to='+'+CONF_TWILIO['num_to'],
                from_='+'+CONF_TWILIO['num_from'],
                body='terminating runner...'
            )
        SystemExit()


def _run_import_docs():
    """
    Given the xslt file, the medline files will be transformed and used to 
    update the existing record or create new record in the Solr core (medline)
    """
    # - read xsl file
    if not os.path.isfile(PATHS['xsl-medline']):
        log('ERROR', 'xsl-medline [{}] cannot be found'.
                      format(PATHS['xsl-medline']), die=True, printout=True)
    else:
        log('DEBUG', 'reading xsl file for medline xml files')

    try:
        xslt = et.parse(PATHS['xsl-medline'])
        transformer = et.XSLT(xslt)
    except:
        e = sys.exc_info()[0]
        log('ERROR', 'xsl parsing error: {}'.format(e), printout=True)

    # read all doc source files (*.gz) in part[1..5] directories
    # (total num of files must be 888)
    doc_files = []
    for root, dirs, files in os.walk(PATHS['data-medline']):
        if not re.match(r"part[1-5]", root.split(os.sep)[-1]):
            continue
        for file in files:
            if not file.endswith('gz'):
                continue
            doc_files.append(os.path.join(root, file))

    # if skip_files is given, read the list
    skip_files = []
    if os.path.isfile(args.skip_files):
        with open(args.skip_files) as f:
            skip_files = f.read().splitlines()
        skip_fh = open(args.skip_files, 'a', buffering=1)

    import gzip

    for i, file in enumerate(doc_files):
        attempts = 3
        if file in skip_files:
            log('WARNING',
                'file already imported. skipping... {}'.format(file),
                printout=True)
            sys.stdout.flush()
            continue
        log('INFO', 'parsing a doc file {}'.format(file))

        # - convert to a solr update xml format
        doc_trans = transformer(et.parse(gzip.open(file)))

        # - run update with the converted file
        url = "http://localhost:8983/solr/medline/update?commit=true"
        headers = {'content-type': 'text/xml; charset=utf-8'}
        while attempts > 0:
            try:
                response = requests.post(url, data=et.tostring(doc_trans),
                                         headers=headers)
            except requests.exceptions.RequestException as e:
                print(response)
                log('ERROR', 'request exception: {}'.format(e),
                    die=True, printout=True)

            if response.status_code != 200:
                attempts -= 1
                log('ERROR', 'requests error:')
                log('ERROR', response.text)
                response.raise_for_status()
                if attempts < 0:
                    log('CRITICAL', 'terminating', die=True, printout=True)
            else:
                # - log the results
                log('INFO', 'importing doc files in progress {}/{}'.
                    format(i+1, len(doc_files)), printout=True)
                skip_fh.write(file + '\n')

                if args.sms and (i+1) % 100 == 0:
                    msg = twilio_cl.messages.create(
                        to='+'+CONF_TWILIO['num_to'],
                        from_='+'+CONF_TWILIO['num_from'],
                        body='importing doc files {}/{}'.format(i+1, len(doc_files))
                    )

                    log('INFO', 'progress message sent ({})'.format(msg.sid))
                break
    log('INFO', 'importing medline documents completed', printout=True)


def _run_import_trials():
    """
    Given corresponding xslt file, the trials xml files are transformed and 
    used to update the existing record or create new record in the Solr core 
    (trials)
    """
    batch = 500
    url = "http://localhost:8983/solr/trials/update?commit=true"

    # - read xsl file
    if not os.path.isfile(PATHS['xsl-trial']):
        log('ERROR', 'xsl-trial [{}] cannot be found'.
            format(PATHS['xsl-trial']), die=True, printout=True)
    else:
        log('DEBUG', 'reading xsl file for clinical trials xml files')

    import lxml.etree as et  # for xml transformation
    try:
        xslt = et.parse(PATHS['xsl-trial'])
        transformer = et.XSLT(xslt)
    except:
        e = sys.exc_info()[0]
        log('ERROR', 'xsl parsing error: {}'.format(e), printout=True)

    # read all trial source files (*.xml) in trial data sub-directories
    # (total num of files must be 241006)
    trial_files = []
    for root, dirs, files in os.walk(PATHS['data-trials']):
        if not re.match(r"\d+", root.split(os.sep)[-1]):
            continue
        for file in files:
            if not file.endswith('xml'):
                continue
            trial_files.append(os.path.join(root, file))

    # if skip_files is given, read the list
    skip_files = []
    if args.skip_files and os.path.isfile(args.skip_files):
        with open(args.skip_files) as f:
            skip_files = f.read().splitlines()
        skip_fh = open(args.skip_files, 'a', buffering=1)

    docs_collated = 0
    skipped_files = 0
    completed_files = 0
    for i, file in enumerate(trial_files):
        attempts = 3
        if file in skip_files:
            skipped_files += 1
            if skipped_files % 1000 == 0:
                log('INFO', 'skipping files [{}/{}]'.format(skipped_files,
                                                            len(skip_files)))
            continue
        log('INFO', 'parsing a trial file {}'.format(file))

        if docs_collated == 0:
            req = et.Element('add')

        # - transform trial xml to solr update format
        trial_trans = transformer(et.parse(file))
        # - pre-indexing nlp process
        age_normalize(trial_trans)
        if docs_collated < batch:
            req.append(trial_trans.getroot())
            docs_collated += 1

        # - run update, if docs_collated reached batch or end of files
        if (docs_collated == batch or i == len(trial_files)-1):
            docs_collated = 0
            headers = {'content-type': 'text/xml; charset=utf-8'}

            while attempts > 0:
                try:
                    response = requests.post(url, data=et.tostring(req),
                                             headers=headers)
                except requests.exceptions.RequestException as e:
                    print(response)
                    log('ERROR', 'request exception: {}'.format(e))
                    log('ERROR', response, die=True, printout=True)

                if response.status_code != 200:
                    attempts -= 1
                    log('ERROR', 'requests error:')
                    log('ERROR', response.text)
                    log('ERROR', 'data: \n' + str(et.tostring(req)))
                    response.raise_for_status()
                    if attempts < 0:
                        log('CRITICAL', 'terminating', die=True, printout=True)
                else:
                    completed_files += 1
                    # - log the results
                    log('INFO', 'importing trial files in progress {}/{}'.
                        format(i+1, len(trial_files)), printout=True)
                    if args.skip_files:
                        skip_fh.write(file + '\n')

                    if args.sms and completed_files % 5000 == 0:
                        msg = twilio_cl.messages.create(
                            to='+'+CONF_TWILIO['num_to'],
                            from_='+'+CONF_TWILIO['num_from'],
                            body='importing trial files {}/{}'.
                                format(i+1, len(trial_files))
                        )

                        log('INFO', 'progress message sent ({})'.format(msg.sid))
                    break
    log('INFO', 'importing trials completed', printout=True)


def age_normalize(dom):
    # normalize age pattern into days (ex. 10 Years => 10 * 12 * 365)
    # age pattern
    r = r"([1-9][0-9]*) (Year|Years|Month|Months|Week|Weeks|Day|Days|Hour" \
        r"|Hours|Minute|Minutes)"
    units = {
        'Year': 12 * 365,
        'Years': 12 * 365,
        'Month': 30,
        'Months': 30,
        'Week': 7,
        'Weeks': 7,
        'Day': 1,
        'Days': 1,
        'Hour': 1 / 24,
        'Hours': 1 / 24,
        'Minute': 1 / 24 / 60,
        'Minutes': 1 / 24 / 60,
    }

    min_age = dom.xpath("/doc/field[@name='eligibility-minimum_age']")[0].text
    min_age_norm = 0
    if min_age != 'N/A' and min_age:
        m = re.match(r, min_age)
        min_age_norm = int(m.group(1)) * units[m.group(2)]

    max_age = dom.xpath("/doc/field[@name='eligibility-maximum_age']")[0].text
    max_age_norm = 200 * units['Years']
    if max_age != 'N/A' and max_age:
        m = re.match(r, max_age)
        max_age_norm = int(m.group(1)) * units[m.group(2)]

    fld_min = et.Element("field", name="eligibility-min_age_norm", type="float")
    fld_min.text = str(min_age_norm)
    fld_max = et.Element("field", name="eligibility-max_age_norm", type="float")
    fld_max.text = str(max_age_norm)

    dom.getroot().append(fld_min)
    dom.getroot().append(fld_max)

    return dom

if __name__ == '__main__':
    # initialize argparser
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="run different tasks",
                        choices=['import_docs', 'import_trials'])
    parser.add_argument("-s", "--sms",
                        help="send sms notification with progress status",
                        action="store_true")
    parser.add_argument("--skip_files", help="skip files already imported")
    args = parser.parse_args()

    # initialize logger
    logging.basicConfig(filename=PATHS['logfile'], filemode='a',
                        level=logging.INFO,
                        format='%(asctime)s %(levelname)s:: %(message)s')
    log('INFO', '-'*80 + '\ncommand requested: ' + args.command, printout=True)

    # initialize twilio client
    twilio_cl = Client(CONF_TWILIO['account_sid'], CONF_TWILIO['auth_token'])

    if args.command == 'import_docs':
        _run_import_docs()
    elif args.command == 'import_trials':
        _run_import_trials()
