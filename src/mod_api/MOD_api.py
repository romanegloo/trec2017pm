#!/usr/bin/env python3

import requests
import json

url = "https://meshb.nlm.nih.gov/api/MOD"


class Client(object):
    def __init__(selfself):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_mesh(self, q_str):
        meshes = []
        r = requests.post(url, json={"input": q_str})
        # return meshHeadings only, if r.status is fine
        try:
            resp = json.loads(r.json()['body'])
            meshes = [t['Term'] for t in resp['MoD_Raw']['Term_List']]
        except:
            return None
        return meshes

if __name__ == '__main__':
    test_query = "pancreatic ductal adenocarcinoma"
    test_query = 'NF2'
    test_query = "gene transcription"
    test_query = "k322"
    test_query = "E17K"
    with Client() as mod:
        meshes = mod.get_mesh(test_query)
        print(meshes)
