#!/usr/bin/env python3

import os
from itertools import combinations
from collections import OrderedDict
from Trec2017pm import utils

PATH_RUNS = "/home/jno236/projects/trec2017/var/RUNS"
PATH_REL = "/home/jno236/projects/trec2017/data/cosmic_ref"
topics_agg = os.path.join(PATH_RUNS, 'RUN_AGG.out')

def analyze_results():
    run_files = [None] * 5
    for i in [1, 2, 4]:
        run_files[i] = os.path.join(PATH_RUNS, 'RUN{}-t.out'.format(i))

    # read in COSMIC relevance files
    ref = [[] for i in range(31)]
    for i in range(1, 31):
        ref_file = os.path.join(PATH_REL, "t{}.cosmic".format(i))
        with open(ref_file) as fin:
            ref[i] = fin.read().splitlines()
            print("reading ref files {} lines in {}".format(len(ref[i]), i))

    for r1, r2 in combinations(range(1, 5), 2):
        list1 = [[] for i in range(31)]  # 30 topics
        list2 = [[] for i in range(31)]  # 30 topics
        with open(run_files[r1]) as fin:
            for line in fin:
                q_no, _, doc_no, pos, score, run_name = line.split()
                list1[int(q_no)].append(doc_no)
        with open(run_files[r2]) as fin:
            for line in fin:
                q_no, _, doc_no, pos, score, run_name = line.split()
                list2[int(q_no)].append(doc_no)

        # intersection among top 10
        gammas = []
        for t in range(1, 31):

            # intersection of top 30 documents
            insect30 = set(list1[t][:31]).intersection(set(list2[t][:31]))
            cnt_top30 = [0, 0, 0]
            for d in insect30:
                if d in ref[t]:
                    cnt_top30[0] += 1
            # only seen in list1
            for d in list1[t][:31]:
                if d in ref[t]:
                    cnt_top30[1] += 1
            cnt_top30[1] -= cnt_top30[0]
            # only seen in list2
            for d in list2[t][:31]:
                if d in ref[t]:
                    cnt_top30[2] += 1
            cnt_top30[2] -= cnt_top30[0]
            gamma = (cnt_top30[1] + cnt_top30[2]) / (1 + cnt_top30[0])
            gammas.append(gamma)
            print("Intersection of #{}: {} (only seen in list1 {}, in list2 {})"
                  ", gamma={:.4f}"
                  "".format(t, cnt_top30[0], cnt_top30[1], cnt_top30[2], gamma))
        print("[{}, {}] Stats: gamma={}"
              "".format(r1, r2, sum(gammas)/float(len(gammas))))


def aggregate_results(r1, r2):
    r1_file = os.path.join(PATH_RUNS, 'RUN{}-t.out'.format(r1))
    r2_file = os.path.join(PATH_RUNS, 'RUN{}-t.out'.format(r2))

    # save two lists of pairs (doc_no, score)
    list1 = []
    list2 = []
    with open(r1_file) as fin:
        for line in fin:
            q_no, _, doc_no, pos, score, run_name = line.split()
            list1.append((int(q_no), doc_no, float(score)))
    with open(r2_file) as fin:
        for line in fin:
            q_no, _, doc_no, pos, score, run_name = line.split()
            list2.append((int(q_no), doc_no, float(score)))

    # get the min max for score normalization
    score_range_l1 = [[9999, 0] for i in range(31)]
    score_range_l2 = [[9999, 0] for i in range(31)]
    for q_no, doc_no, score in list1:
        if score < score_range_l1[q_no][0]:
            score_range_l1[q_no][0] = score
        if score > score_range_l1[q_no][1]:
            score_range_l1[q_no][1] = score
    for q_no, doc_no, score in list2:
        if score < score_range_l2[q_no][0]:
            score_range_l2[q_no][0] = score
        if score > score_range_l2[q_no][1]:
            score_range_l2[q_no][1] = score

    # create dictionary with aggregated normalized scores
    new_result = [{} for i in range(31)]
    for q_no, doc_no, score in list1:
        mm = score_range_l1[q_no]
        new_result[q_no][doc_no] = (score - mm[0]) / (mm[1] - mm[0])
    for q_no, doc_no, score in list2:
        mm = score_range_l2[q_no]
        score2 = (score - mm[0]) / (mm[1] - mm[0])
        if doc_no in new_result[q_no]:
            new_result[q_no][doc_no] += score2
        else:
            new_result[q_no][doc_no] = score2

    # rank the newly created list, and save with up to 1,000 records
    for i in range(1, 31):
        d = new_result[i]
        ordered = OrderedDict(sorted(d.items(), key=lambda t: t[1],
                                     reverse=True))
        new_result[i] = ordered

    # save the aggregated result
    with open(topics_agg, 'w') as fout:
        for i in range(1, 31):
            cnt_rec = 0
            for d, s in new_result[i].items():
                fout.write("{} Q0 {} {} {:.6f} RUN_AGG\n"
                           "".format(i, d, cnt_rec, s))
                if cnt_rec >= 999:
                    break
                else:
                    cnt_rec += 1

if __name__ == "__main__":
    # comapare results and find a pair that captures features in a
    # distinctive way
    # analyze_results()

    # aggregate the results and create the merges ranked list, then evaluate
    aggregate_results(1, 4)  # aggregate RUN2 and RUN4

    # evaluate
    # utils.run_evaluators(topics_agg)