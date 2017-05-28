""" log wrapper """
import os
import sys
import logging
import argparse
from twilio.rest import Client
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config as cfg


def singleton(cls):
    instances = {}
    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return getinstance

@singleton
class Logger(object):
    def __init__(self):
        # initialize logger
        logging.basicConfig(filename=cfg.PATHS['logfile'], filemode='a',
                            level=logging.INFO,
                            format='%(asctime)s %(levelname)s:: %(message)s')
        self.log('INFO', '-'*80 + '\ncommand requested: ' + cfg.command,
                 printout=True)

        # initialize twilio client
        self.twilio_cl = Client(cfg.CONF_TWILIO['account_sid'],
                                cfg.CONF_TWILIO['auth_token'])

    def log(self, level, msg, die=False, printout=False):
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
            if cfg.sms:
                msg = self.twilio_cl.messages.create(
                    to='+' + cfg.CONF_TWILIO['num_to'],
                    from_='+' + cfg.CONF_TWILIO['num_from'],
                    body='terminating runner...'
                )
            SystemExit()

    def sms(self, msg):
        """ send sms message to me """
        res = self.twilio_cl.message.create(
            to='+' + cfg.CONF_TWILIO['num_to'],
            from_='+' + cfg.CONF_TWILIO['num_from'],
            body=msg)
        self.log('INFO', 'progress message sent ({})'.format(res.sid))
