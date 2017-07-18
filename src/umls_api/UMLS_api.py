#!/usr/bin/env python3

import requests
from pyquery import PyQuery as pq
import json


apikey = "5cd21481-a538-4385-ad98-873b096397f5"
service_version = "current"
uri_service = "http://umlsks.nlm.nih.gov"
uri_search = "https://uts-ws.nlm.nih.gov"
uri_auth = "https://utslogin.nlm.nih.gov"
endpoint = {
    'auth': uri_auth + "/cas/v1/api-key",
    'search': uri_search + "/rest/search/" + service_version,
    'content': uri_search + "/rest/content/" + service_version
}


class Client(object):
    def __init__(self):
        # get the URL for POST calls from the auth endpoint
        self.tgt = self.get_tgt(apikey)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_tgt(self, key):
        """get tgt (ticket granting ticket) """
        params = {'apikey': key}
        h = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            "User-Agent": "python"}
        r = requests.post(endpoint['auth'], data=params, headers=h)
        d = pq(r.text)
        tgt = d.find('form').attr('action')
        if tgt is None:
            raise SystemError("failed to authenticate")
        return tgt

    def get_st(self):
        """get st (service ticket) which is mandatory for each search request"""
        if self.tgt is None:
            raise SystemError("authentication is not established")
        params = {'service': uri_service}
        h = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            "User-Agent": "python"}
        r = requests.post(self.tgt, data=params, headers=h)
        return r.text

    def get_cuis(self, term, sts=None):
        ticket = self.get_st()
        q = {
            'ticket': ticket,
            'sabs': 'NCI',
            'string': term,
            'pageNumer': 1,
            'pageSize': 5
        }
        r = requests.get(endpoint['search'], params=q)
        r.encoding = 'utf-8'
        items = json.loads(r.text)
        # print(json.dumps(items, indent=4))
        jsonData = items['result']
        return jsonData

    def get_atoms(self, cui):
        ticket = self.get_st()
        q = {
            'ticket': ticket,
            'sabs': 'NCI',
        }
        r = requests.get("{}/CUI/{}/atoms?language=ENG"
                         "".format(endpoint['content'], cui), params=q)
        r.encoding = 'utf-8'
        if r.status_code != 200:
            return None
        items = json.loads(r.text)
        # print(json.dumps(items, indent=4))
        jsonData = items['result']
        return jsonData
