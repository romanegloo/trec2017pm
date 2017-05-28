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

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config
from Trec2017pm import logger, solr

def update_obj(dst, src):
    """helper function in order to use 'config' namespace as global 
    parameters among module screipts"""
    for key, value in src.items():
        setattr(dst, key, value)

if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="run different tasks",
                        choices=['import_docs', 'import_trials'])
    parser.add_argument("-s", "--sms",
                        help="send sms notification with progress status",
                        action="store_true")
    parser.add_argument("--skip_files", help="skip files already imported")
    args = parser.parse_args()
    update_obj(config, vars(args))

    # initialize logger, solr
    logger = logger.Logger()

    if args.command == 'import_docs':
        solr.run_import_docs()
    elif args.command == 'import_trials':
        solr.run_import_trials()
