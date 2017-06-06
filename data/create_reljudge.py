import os

t = range(0, 31)
path = 'cosmic_ref'

for t in range(1, 31):
    #read files
    with open(os.path.join(path, 't{}.cosmic'.format(t))) as inf,\
            open(os.path.join(path, 'rel_file.cosmic'), 'a') as trec,\
            open(os.path.join(path, 'rel_file_s.cosmic'), 'a') as sample:
        docs = inf.read().splitlines()

        for doc in docs:
            trec.write("{} 0 {} 1\n".format(t, doc))
            sample.write("{} 0 {} cat0 1\n".format(t, doc))


