#!/usr/bin/env python3

import os

template_dir = '../var/q_tmpl-exp12'

for i in range(1, 31):
    file = os.path.join(template_dir, 'a{}.query'.format(i))
    q = ''
    if os.path.exists(file):
        with open(file) as f_query:
            q = f_query.read()
    q = q.replace("0.6171", "<WT1>")  # disease name
    q = q.replace("1.3954", "<WT2>")  # disease meshHeading
    q = q.replace("1.7781", "<WT3>")  # gene name
    q = q.replace("0.9272", "<WT4>")  # gene meshHeading
    q = q.replace("0.9553", "<WT5>")  # mutation name
    q = q.replace("2.2484", "<WT6>")  # mutation meshHeading
    q = q.replace("5.8368", "<WT7>")  # demographic
    q = q.replace("0.2486", "<WT8>")  # conjunctive
    with open(os.path.join(template_dir, 'a{}.template'.format(i)), 'w') \
            as f_tmpl:
        f_tmpl.write(q)
    print("template #{} created".format(i))

