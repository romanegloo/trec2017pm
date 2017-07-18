#!/usr/bin/env python3

import os

template_dir = '../var/res-weight_template_2'

for i in range(1, 31):
    file = os.path.join(template_dir, 'a{}.query'.format(i))
    q = ''
    if os.path.exists(file):
        with open(file) as f_query:
            q = f_query.read()
    q = q.replace("1.111", "<WT1>")
    q = q.replace("2.222", "<WT2>")
    q = q.replace("3.333", "<WT3>")
    q = q.replace("4.444", "<WT4>")
    q = q.replace("5.555", "<WT5>")
    q = q.replace("6.666", "<WT6>")
    q = q.replace("7.777", "<WT7>")
    with open(os.path.join(template_dir, 'a{}.template'.format(i)), 'w') \
            as f_tmpl:
        f_tmpl.write(q)
    print("template #{} created".format(i))

