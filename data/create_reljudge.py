import os

t = range(0, 31)
path = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(path, 'cosmic_ref/rel_file.cosmic'), 'w') as trec, \
        open(os.path.join(path, 'cosmic_ref/rel_file_s.cosmic'), 'w') as sample:
    for t in range(1, 31):
        returned = set()
        #read files
        with open(os.path.join(path, 'cosmic_ref/t{}.cosmic'.format(t))) as inf:
            docs = inf.read().splitlines()
            for doc in docs:
                if not doc.startswith("#") and len(doc) > 0:
                    returned.add(doc)

            for doc in returned:
                trec.write("{} 0 {} 1\n".format(t, doc))
                sample.write("{} 0 {} cat0 1\n".format(t, doc))
