import os
import re
import sys
import lxml.etree as et
from nltk import sent_tokenize
from itertools import chain
import subprocess
from nltk.corpus import stopwords
import itertools
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config as cfg
from Trec2017pm.logger import Logger
from pymetamap import MetaMap
from umls_api import UMLS_api
from mod_api import MOD_api

logger = Logger()  # singleton
mm = MetaMap.get_instance('/opt/public_mm/bin/metamap16')

stopwords = stopwords.words('english')
extra_stopwords = ['gene']


def escape_special_chars(text, esc_chars="+-^~:", rm_chars="&|!(){}[]*?\/"):
    for chr in rm_chars:
        text = text.replace(chr, '')
    for chr in esc_chars:
        text = text.replace(chr, '\\' + chr)
    return text


def age_normalize(dom):
    """normalize age pattern into days (ex. 10 Years => 10 * 365)"""
    units = {
        'Year': 365,
        'Years': 365,
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
    # age pattern
    pattern = r"([1-9]*[0-9]+) (Year|Years|Month|Months|Week|Weeks|" \
              r"Day|Days|Hour|Hours|Minute|Minutes)"

    min_age = dom.xpath("/doc/field[@name='eligibility-minimum_age']")[0].text
    min_age_norm = 0
    if min_age != 'N/A' and min_age:
        m = re.match(pattern, min_age)
        min_age_norm = int(m.group(1)) * units[m.group(2)]

    max_age = dom.xpath("/doc/field[@name='eligibility-maximum_age']")[0].text
    max_age_norm = 200 * units['Years']
    if max_age != 'N/A' and max_age:
        m = re.match(pattern, max_age)
        max_age_norm = int(m.group(1)) * units[m.group(2)]

    fld_min = et.Element("field", name="eligibility-min_age_norm", type="float")
    fld_min.text = str(min_age_norm)
    fld_max = et.Element("field", name="eligibility-max_age_norm", type="float")
    fld_max.text = str(max_age_norm)

    dom.getroot().append(fld_min)
    dom.getroot().append(fld_max)

    return dom


def get_meshheading(phrase):
    concepts, error = mm.extract_concepts([phrase], **cfg.CONF_MM)
    # assuming that the first concept is the most related one with the
    # highest score
    if len(concepts):
        return concepts[0].preferred_name
    else:
        return None


def extract_cuis(docs):
    """this takes so much time for parsing the entire document collection.
    Moving forward to exploit umls_api synonyms using its rest-api"""
    extract_from = ['subject', 'abstract']
    for d in docs.xpath("//doc"):
        text = []
        for field in extract_from:
            for elm in d.xpath("./field[@name='{}']".format(field)):
                if elm.text and len(elm.text) > 0:
                    text.append(' '.join(sent_tokenize(elm.text)))
        concepts, error = \
            mm.extract_concepts([' '.join(text)], **cfg.CONF_MM)

        for c in concepts:
            # print("{:>6} | {} => {} [{}, semtypes:{}]"
            #       "".format(c.score, c.trigger, c.preferred_name, c.cui, c.semtypes))
            cui = et.Element("field", name="CUI")
            try:
                cui.text = c.cui
            except AttributeError as e:
                continue
            d.append(cui)
    return docs


def parse_topics(path, target='a'):
    """query builder: read and pre-process the given topics and build queries

    example)
    <topics>
        <topic number="1">
            <disease>Liposarcoma</disease>
            <gene>CDK4 Amplification</gene>
            <demographic>38-year-old male</demographic>
            <other>GERD</other>
        </topic>
        ...
    </topics>
    """
    if not os.path.isfile(path):
        logger.log('ERROR', 'topic file cannot be found', die=True,
                   printout=True)
    queries = []
    doc = et.parse(path)
    # preprocessing
    for tidx, t in enumerate(doc.iterfind('.//topic')):
        if cfg.topic and tidx+1 != int(cfg.topic):
            continue
        logger.log('INFO', 'Topics #{}: parsing'.format(tidx+1) + '-'*30,
                   printout=True)
        q_terms = []
        t_no = tidx + 1
        q_terms.append(parse_disease(t[0].text, t_no, target))
        q_terms.append(parse_gene(t[1].text, t_no, target))
        q_terms.append(parse_demographic(t[2].text, target))
        if not cfg.CONF_SOLR['enable_conj_uprank']:
            q_terms.append(parse_cjt_major(t, target))

        queries.append({'query': ' '.join(q_terms)})
    return queries


def parse_disease(val, t_no, target):
    """
    given disease name (ex. "Pancreatic Cancer"), build query string by its
    target source accordingly:
        ex. +(d_name)^xx ([meshHeading|keyword]:(d_mesh))^yy

    :param val: string input
    :param target: ['a', 't'] for 'a'rticles or 't'rials
    :return: string query phrase for disease name
    """
    logger.log('INFO', '    * disease_name [{}]'.format(val))
    d_name = []
    d_mesh = []
    # query expansion (umls)
    if cfg.CONF_SOLR['qe_umls']:
        # append synonyms in the disease name group
        cache_file = "{}/t{}-disease.umls".format(cfg.PATHS['cache'], t_no)
        qe = {'atoms': [], 'preferred_name': ''}
        if not os.path.exists(cache_file):
            with UMLS_api.Client() as client:
                cuis = client.get_cuis(val)
                atoms = client.get_atoms(cuis['results'][0]['ui'])
                mesh_preferred = get_meshheading(cuis['results'][0]['name'])
                atom_names = set()
                for a in atoms:
                    atom_names.add(a['name'].lower())
                qe['atoms'] = list(atom_names)
                qe['preferred_name'] = mesh_preferred
            # write qe to a chache file
            with open(cache_file, 'w') as fout:
                json.dump(qe, fout)
        else:
            with open(cache_file) as fin:
                try:
                    qe = json.load(fin)
                except:
                    pass
        d_name.extend(qe['atoms'])
        d_mesh.append(qe['preferred_name'])
    # query expansion (mod)
    if cfg.CONF_SOLR['qe_MoD']:
        cache_file = "{}/t{}-disease.mod".format(cfg.PATHS['cache'], t_no)
        qe = []  # list of mesh headings
        if not os.path.exists(cache_file):
            with MOD_api.Client() as client:
                qe = client.get_mesh(val)
            with open(cache_file, 'w') as fout:
                json.dump(qe, fout)
        else:
            with open(cache_file) as fin:
                try:
                    qe = json.load(fin)
                except:
                    pass
        d_name.extend(qe)
        d_mesh.extend(qe)

    # build query phrase
    if len(d_name) == 0:
        d_name.append(val)
    q_phrase = "+({}){}{}".format(' '.join(['"' + t + '"' for t in d_name]),
                                  cfg.CONF_SOLR['wt_multiplier'],
                                  cfg.CONF_SOLR['wt_disease'])
    if len(d_mesh) > 0:
        field = 'keyword' if target == 't' else 'meshHeading'
        q_phrase += " {}:({}){}{}".format(field, ' '.join(['"' + t + '"' \
                                                           for t in d_mesh]),
                                          cfg.CONF_SOLR['wt_multiplier'],
                                          cfg.CONF_SOLR['wt_meshDisease'])
    return q_phrase


def parse_gene(val, t_no, target):
    """
    parse gene field from the topics and build a query
    patterns found as below:
        - gene_id
        - gene_id (mutation_id)
        - gene_id [Amplification|Fusion|Inactivating|Loss|Deletion]

    a query will look like below:
        (+((gene_name_i)^w1 (mutation_name_i)^w2)
            [meshHeading|keyword]:(gene_mesh_i)^w3
            [meshHeading|keyword]:(mutation_mesh_i)^w4)...

    :param val: original input string about gene and gene mutation
    :param target: 'a'rticles or 't'rials
    :return: query built from the given gene information
    """
    # mutation_types = ['amplification', 'fusion', 'inactivating', 'loss',
    #                   'deletion', 'trascription']
    # meshHeadings_gene = []
    # meshHeadings_mut = []
    # q_phrase = []
    # q_gene = []
    # q_mutation = set()
    # for gene_phrase in val.split(','):
    #     gene_phrase = gene_phrase.strip().lower()
    #     pattern_found = False
    #     if not pattern_found:
    #         # ex) braf (v600e)
    #         m = re.match(r"([\w-]+)\s\((\w+)\)", gene_phrase)
    #         if m:
    #             gene_names = m.group(1).split('-')
    #             mutations = m.group(2).split()
    #             pattern_found = True
    #     if not pattern_found:
    #         # ex) KIT Exon 9 (A502_Y503dup)
    #         m = re.match(r"^([\w\s]+)\s\(([\w\s_]+)\)$", gene_phrase)
    #         if m:
    #             gene_names = m.group(1).split('-')
    #             mutations = m.group(2).split()
    #             pattern_found = True
    #     if not pattern_found:
    #         # ex) CDK4 amplification
    #         m = re.match(r"^([\w-]+)\s({})$"
    #                      "".format('|'.join(mutation_types)), gene_phrase)
    #         if m:
    #             gene_names = m.group(1).split('-')
    #             mutations = m.group(2).split()
    #             pattern_found = True
    #     if not pattern_found:
    #         # otherwise; ex) NTRK1
    #         gene_names = gene_phrase.split('-')
    #         mutations = []
    #     logger.log('INFO', '    * gene_name [{}] mutation [{}]'.
    #                format(gene_names, mutations))
    #
    #     # UMLS query expansion
    #     if 'gene' in cfg.CONF_SOLR['umls_qe']:
    #         with UMLS_api.Client() as client:
    #             # handle gene names
    #             for gene in gene_names:
    #                 terms = set([gene.lower()])  # add the original gene name
    #                 cuis = client.get_cuis(gene)
    #                 mesh_preferred = get_meshheading(cuis['results'][0]['name'])
    #                 if mesh_preferred is not None:
    #                     meshHeadings_gene.append(mesh_preferred)
    #                 atoms = client.get_atoms(cuis['results'][0]['ui'])
    #                 if atoms is None:
    #                     q_gene.append(gene.lower())
    #                     # q_phrase.append(gene.lower())
    #                     continue
    #                 for a in atoms:
    #                     t = a['name'].lower()
    #                     # remove a broader concept, mostly captured in a parenthesis
    #                     t = re.sub(r'\(.*\)', '', t)
    #                     # remove stop words
    #                     t = [a for a in t.split()
    #                          if a not in stopwords and a not in extra_stopwords]
    #                     # remove common words ('gene')
    #                     terms.add(' '.join(t))
    #                 for term in terms:
    #                     q_gene.append(
    #                         '"' + term + '"' if len(term.split()) > 1 else term)
    #                 logger.log('DEBUG',
    #                            "    \"{}\" expands [{}]".format(gene, terms))
    #
    #             # handle mutation
    #             for gene, mut in itertools.product(gene_names, mutations):
    #                 if mut in mutation_types:
    #                     q_mutation.add(mut.lower())
    #                     continue
    #                 q_mutation.add(mut.lower())
    #                 num_clue = re.search('\d+', mut).group()
    #                 mesh_preferred = get_meshheading(gene + ' ' + mut)
    #                 if mesh_preferred is not None:
    #                     meshHeadings_mut.append(mesh_preferred)
    #                 cuis = client.get_cuis(gene + ' ' + mut)
    #                 atoms = client.get_atoms(cuis['results'][0]['ui'])
    #                 if atoms is None:
    #                     continue
    #                 terms = set()  # add the original mutation name
    #                 for a in atoms:
    #                     t = a['name'].lower()
    #                     # remove a broader concept, mostly in a parenthesis
    #                     t = re.sub(r'\(.*\)', '', t)
    #                     # remove stopwords
    #                     t = [a for a in t.split()
    #                          if a not in stopwords and a not in extra_stopwords]
    #                     # extract the key token
    #                     # ex. from np_004963.1:p.val617phe to val617phe
    #                     for t_ in t:
    #                         for tok in re.findall(r"\w+", t_):
    #                             if re.search(r'{}'.format(num_clue), tok):
    #                                 terms.add(tok)
    #                 for x in terms:
    #                     q_mutation.add(x)
    #                 logger.log('DEBUG',
    #                            "    \"{}\" expands [{}]".format(mut, terms))
    #     else:
    #         q_gene.append(' '.join(gene_names))
    #         if mutations is not None:
    #             q_mutation.add(' '.join(mutations))
    # if cfg.CONF_SOLR['enable_conj_uprank']:
    #     q_phrase = ''
    #     if len(q_gene) > 0:
    #         q_phrase += "+({}){}{}".format(' '.join(q_gene),
    #                                        cfg.CONF_SOLR['wt_multiplier'],
    #                                        cfg.CONF_SOLR['wt_gene'])
    #     if len(q_mutation) > 0:
    #         q_phrase += " +({}){}{}".format(' '.join(q_mutation),
    #                                         cfg.CONF_SOLR['wt_multiplier'],
    #                                         cfg.CONF_SOLR['wt_mutation'])
    # else:
    #     q_phrase = "+("
    #     if len(q_gene) > 0:
    #         q_phrase += "({}){}{}".format(' '.join(q_gene),
    #                                       cfg.CONF_SOLR['wt_multiplier'],
    #                                       cfg.CONF_SOLR['wt_gene'])
    #     if len(q_mutation) > 0:
    #         q_phrase += " ({}){}{}".format(' '.join(q_mutation),
    #                                        cfg.CONF_SOLR['wt_multiplier'],
    #                                        cfg.CONF_SOLR['wt_mutation'])
    #     q_phrase += ")"
    #
    # field = 'keyword' if target == 't' else 'meshHeading'
    # if len(meshHeadings_gene) > 0:
    #     q_phrase += " ("
    #     for msh in meshHeadings_gene:
    #         q_phrase += field + ':"' + msh + '" '
    #     q_phrase += ")" + cfg.CONF_SOLR['wt_multiplier'] + \
    #                 str(cfg.CONF_SOLR['wt_meshGene'])
    # if len(meshHeadings_mut) > 0:
    #     q_phrase += " ("
    #     for msh in meshHeadings_mut:
    #         q_phrase += field + ':"' + msh + '" '
    #     q_phrase += ")" + cfg.CONF_SOLR['wt_multiplier'] + \
    #                 str(cfg.CONF_SOLR['wt_meshMutation'])
    #
    # return q_phrase

    # read-in caches
    qe_umls = dict()
    qe_mod = dict()
    update_umls = False
    update_mod = False
    cache_umls = "{}/t{}-gene.umls".format(cfg.PATHS['cache'], t_no)
    cache_mod = "{}/t{}-gene.mod".format(cfg.PATHS['cache'], t_no)
    if cfg.CONF_SOLR['qe_umls'] and os.path.exists(cache_umls):
        with open(cache_umls) as fin:
            try:
                qe_umls = json.load(fin)
            except:
                pass
    if cfg.CONF_SOLR['qe_MoD'] and os.path.exists(cache_mod):
        with open(cache_mod) as fin:
            try:
                qe_mod = json.load(fin)
            except:
                pass

    # parse gene tag first
    gene_group = []
    for gene_phrase in val.split(','):
        gene_phrase = gene_phrase.strip().lower()
        # find a pattern
        #   1. braf (v600e)
        #   2. KIT Exon 9 (A502_Y503dup)
        #   3. EML4-ALK Fusion
        #   4. NTRK1
        pattern_found = False
        if not pattern_found:
            m = re.match(r"([\w-]+)\s\((\w+)\)", gene_phrase)
            if m:
                gene_name = m.group(1)
                mutation = m.group(2)
                pattern_found = True
        if not pattern_found:
            # ex) KIT Exon 9 (A502_Y503dup)
            m = re.match(r"^([\w\s]+)\s\(([\w\s_]+)\)$", gene_phrase)
            if m:
                gene_name = m.group(1)
                mutation = m.group(2)
                pattern_found = True
        if not pattern_found:
            # ex) CDK4 amplification
            mutation_keys = cfg.CONF_MUT_TYPES.keys()
            m = re.match(r"^([\w-]+)\s({})$"
                         "".format('|'.join(mutation_keys)), gene_phrase)
            if m:
                gene_name = m.group(1)
                mutation = m.group(2)
                pattern_found = True
        if not pattern_found:
            # otherwise; ex) NTRK1
            gene_name = gene_phrase
            mutation = ''
        gene_group.append((gene_name, mutation))
        gene_names = gene_name.split('-')
        mut_names = [mutation]  # singleton for now
        logger.log('INFO', '    * gene_name [{}] mutation [{}]'.
                   format(gene_name, mutation))

        # query expansion (umls)
        if cfg.CONF_SOLR['qe_umls']:
            # handle gene
            for gene in gene_names:
                if gene in qe_umls:
                    continue
                client = UMLS_api.Client()
                cuis = client.get_cuis(gene)
                atoms = client.get_atoms(cuis['results'][0]['ui'])
                qe_umls[gene] = {
                    'gene_mesh': [get_meshheading(cuis['results'][0]['name'])]
                }
                atom_names = set()
                for a in atoms:
                    t = a['name'].lower()
                    # remove unnecessary parenthesis part
                    t = re.sub(r'\(.*\)', '', t)
                    # remove stop words
                    t = [a for a in t.split()
                         if a not in stopwords and a not in extra_stopwords]
                    atom_names |= set(t)  # union
                qe_umls[gene]['gene_atoms'] = list(atom_names)
                update_umls = True
            # handle mutation
            for mut in mut_names:
                if len(gene_name.split('-')) > 1 and gene_name not in qe_umls:
                    qe_umls[gene_name] = {
                        'gene_atoms': [],
                        'gene_mesh': []
                    }
                if 'mut_atoms' in qe_umls[gene_name].keys() and \
                   'mut_mesh' in qe_umls[gene_name].keys():
                    continue
                else:
                    qe_umls[gene_name]['mut_atoms'] = []
                    qe_umls[gene_name]['mut_mesh'] = []

                # general mutation type
                if mut in cfg.CONF_MUT_TYPES:
                    qe_umls[gene_name]['mut_atoms'].extend(
                        cfg.CONF_MUT_TYPES[mut])
                    qe_umls[gene_name]['mut_mesh'].extend(
                        cfg.CONF_MUT_TYPES[mut])
                    continue

                # numeric clue (positional information)
                try:
                    num_clue = re.search('\d+', mut).group()
                except:
                    num_clue = '.'
                mesh_preferred = get_meshheading(gene_name + ' ' + mut)
                if mesh_preferred is not None:
                    qe_umls[gene_name]['mut_mesh'].append(mesh_preferred)
                client = UMLS_api.Client()
                cuis = client.get_cuis(mut)
                atoms = client.get_atoms(cuis['results'][0]['ui'])
                if atoms is None:
                    continue
                terms = set()
                for a in atoms:
                    t = a['name'].lower()
                    # remove a broader concept, mostly in a parenthesis
                    t = re.sub(r'\(.*\)', '', t)
                    # remove stopwords
                    t = [a for a in t.split()
                         if a not in stopwords and a not in extra_stopwords]
                    # extract the key token
                    # ex. from np_004963.1:p.val617phe to val617phe
                    for t_ in t:
                        for tok in re.findall(r"\w+", t_):
                            if re.search(r'{}'.format(num_clue), tok):
                                terms.add(tok)
                qe_umls[gene_name]['mut_atoms'].extend(terms)
                update_umls = True

        # query expansion (mod)
        if cfg.CONF_SOLR['qe_MoD']:
            for gene in gene_names:
                if gene in qe_mod:
                    continue
                with MOD_api.Client() as client:
                    qe_mod[gene] = client.get_mesh(gene)
                    update_mod = True
            for mut in mut_names:
                if len(mut) == 0 or mut in qe_mod:
                    continue
                with MOD_api.Client() as client:
                    qe_mod[mut] = client.get_mesh(mut)
                    update_mod = True

    # write updates
    if update_umls:
        with open(cache_umls, 'w') as fout:
            json.dump(qe_umls, fout)
    if update_mod:
        with open(cache_mod, 'w') as fout:
            json.dump(qe_mod, fout)

    # build query phrase
    q_phrase = ''
    for (gene, mut) in gene_group:
        # name
        gene_names = [gene]
        mut_names = [mut]
        if gene in qe_umls:
            gene_names.extend(qe_umls[gene]['gene_atoms'])
            mut_names.extend(qe_umls[gene]['mut_atoms'])
        if gene in qe_mod:
            gene_names.extend(qe_mod[gene])
        if mut in qe_mod:
            mut_names.extend(qe_mod[mut])
        q1 = "+("
        if len(gene_names) > 0:
            q1 += " ({}){}{}".format(
                ' '.join(['"' + t + '"' for t in gene_names]),
                cfg.CONF_SOLR['wt_multiplier'],
                cfg.CONF_SOLR['wt_gene'] )
        if len(mut_names) > 0:
            q1 += " ({}){}{}".format(
                ' '.join(['"' + t + '"' for t in mut_names]),
                cfg.CONF_SOLR['wt_multiplier'],
                cfg.CONF_SOLR['wt_mutation'])
        q1 += ")"

        # mesh
        gene_mesh = []
        mut_mesh = []
        if gene in qe_umls:
            gene_mesh.extend(qe_umls[gene]['gene_mesh'])
            mut_mesh.extend(qe_umls[gene]['mut_mesh'])
        if gene in qe_mod:
            gene_mesh.extend(qe_mod[gene])
        if mut in qe_mod:
            mut_mesh.extend(qe_mod[mut])

        field = 'keyword' if target == 't' else 'meshHeading'
        if len(gene_mesh) > 0:
            q2 = " {}:({}){}{}".format(
                field,
                ' '.join(['"' + t + '"' for t in gene_mesh]),
                cfg.CONF_SOLR['wt_multiplier'],
                cfg.CONF_SOLR['wt_meshGene']
            )
        else:
            q2 = ''
        if len(mut_mesh) > 0:
            q3 = " {}:({}){}{}".format(
                field,
                ' '.join(['"' + t + '"' for t in mut_mesh]),
                cfg.CONF_SOLR['wt_multiplier'],
                cfg.CONF_SOLR['wt_meshMutation']
            )
        else:
            q3 = ''

        q_phrase += '(' + q1 + q2 + q3 + ') '
    return '+' + q_phrase if cfg.CONF_SOLR['enable_conj_uprank'] else q_phrase


def parse_demographic(val, target):
    """
    given demographic info (ex. "33-year-old male"), build query string
    appropriately by its target source.
    <demographic>
        - extract age and sex
        - age maps to MeSH terms

    :param val: string input
    :param target: ['a', 't'] for 'a'rticles or 't'rials
    :return: string query phrase for demographic
    """
    assert target in ['a', 't'], "demographic target is undefined"
    meshHeadings = []
    if target == 'a':
        meshHeadings.append('Humans')
    age_groups_str = ['Infant, Newborn', 'Infant', 'Child, Preschool', 'Child',
                      'Adolescent', 'Adult', 'Middle Aged', 'Aged',
                      'Aged, 80 and over']
    age_groups_num = [0, 1/12, 2, 5, 12, 18, 44, 64, 79]
    pattern = r"(\d+)-year-old (male|female)"
    m = re.match(pattern, val)
    q_terms_age = None
    q_terms_sex = None
    if m:
        age = int(m.group(1))  # in years
        sex = m.group(2)
        logger.log('INFO', '    * age [{}] sex [{}]'. format(age, sex))
        # age
        if age is not None:
            if target == 'a':
                # find corresponding age group (in str)
                g_idx = -1
                for i, g in enumerate(age_groups_num):
                    if age > g:
                        g_idx = i
                    else:
                        break
                meshHeadings.append(age_groups_str[g_idx])
                # q_terms_age = 'meshHeading:"{}"'.format(age_groups_str[g_idx])
            elif target == 't':
                # change year into days and do range search
                days = str(age * 365)
                q_terms_age = \
                    "(eligibility-min_age_norm:[* TO " + days + "]) AND " + \
                    "(eligibility-max_age_norm:[" + days + " TO *])"

        # sex
        if sex is not None:
            if target == 'a':
                if sex == 'male':
                    meshHeadings.append("Male")
                    # q_terms_sex = '(meshHeading:Male)'
                elif sex == 'female':
                    meshHeadings.append("Female")
                    # q_terms_sex = '(meshHeading:Female)'
            elif target == 't':
                if sex == 'male':
                    q_terms_sex = "(eligibility-gender:(Male All))"
                elif sex == 'female':
                    q_terms_sex = "(eligibility-gender:(Female All))"

        # combine query terms
        if target == 'a':
            if len(meshHeadings) > 0:
                q_phrase = '+(' if cfg.CONF_SOLR['enable_conj_uprank'] \
                    else '('
                for mh in meshHeadings:
                    q_phrase += 'meshHeading:"' + mh + '" '
                q_phrase += ')'
                return "{}{}{}".format(q_phrase,
                                       cfg.CONF_SOLR['wt_multiplier'],
                                       cfg.CONF_SOLR['wt_meshDemo'])
            else:
                return ''
        elif target == 't':
            return "({} {})".format(q_terms_sex, q_terms_age)


def parse_cjt_major(val, target):
    disease = val[0].text.lower()
    gene_group = val[1].text

    mutation_types = ['amplification', 'fusion', 'inactivating', 'loss',
                      'deletion', 'trascription']
    query = []
    genes = []
    mutation = []
    for gene_phrase in gene_group.split(','):
        q_terms = list([disease])
        gene_phrase = gene_phrase.strip().lower()
        pattern_found = False
        if not pattern_found:
            # ex) braf (v600e)
            m = re.match(r"([\w-]+)\s\((\w+)\)", gene_phrase)
            if m:
                gene_names = m.group(1).split('-')
                mutations = m.group(2).split()
                pattern_found = True
        if not pattern_found:
            # ex) KIT Exon 9 (A502_Y503dup)
            m = re.match(r"^([\w\s]+)\s\(([\w\s_]+)\)$", gene_phrase)
            if m:
                gene_names = m.group(1).split('-')
                mutations = m.group(2).split()
                pattern_found = True
        if not pattern_found:
            # ex) CDK4 amplification
            m = re.match(r"^([\w-]+)\s({})$"
                         "".format('|'.join(mutation_types)), gene_phrase)
            if m:
                gene_names = m.group(1).split('-')
                mutations = m.group(2).split()
                pattern_found = True
        if not pattern_found:
            # otherwise; ex) NTRK1
            gene_names = gene_phrase.split('-')
            mutations = []
        q_terms.extend(gene_names)
        q_terms.extend(mutations)

        query.append('((' + ') AND ('.join(q_terms) + '))')
    return '(' + ' '.join(query) + ')' + cfg.CONF_SOLR['wt_multiplier'] + \
           str(cfg.CONF_SOLR['wt_conjunctive'])


def evaluate(res, ref):
    """ With the given two lists, compute IR evaluation measurements (infAP, 
    infNDCG)
    
    :param res: ranked list of retreived documents
    :param ref: COSMIC curated relevant document list
    :return: evaluation scores
    """
    # infAP
    last_rank = 0
    num_rel = 0
    for rel_doc in ref:
        try:
            rank = res.index(rel_doc)
            num_rel += 1
            if last_rank < rank:
                last_rank = rank
        except ValueError as e:
            pass

    # infAP = 1 / last_rank + (last_rank - 1) / last_rank * \
    #                         (num_rel / (last_rank - 1)) * \
    #                         ((num_rel + 1e-12) / (num_rel + 2e-12))

    if last_rank > 0:
        infAP = (1 + num_rel) / last_rank
    else:
        infAP = 0

    logger.log('INFO', '=== Evaluation ===')
    logger.log('INFO',
               "Evaluation [num_rel:{}, num_judged:{}, num_retrieved:{}]".
               format(num_rel, len(ref), len(res)))
    logger.log('INFO', 'infAP: {}'.format(infAP))
    return num_rel, infAP


def run_evaluators(path):
    """ run two evaluators (trec_eval and sample_eval for inferred metrics),
    and then store the results for future references. (note only the results
    of articles is available due to its ground truth existence
    :param path: path to the directory of a specific run, or the file of topics
    :return: store evaluation result and return on success
    """
    if not os.path.exists(path):
        return

    # check search result file from the given path
    if os.path.isfile(path):
        resdir = os.path.dirname(path)
        top_docs = path
    else:
        resdir = path
        top_docs = os.path.join(path, 'top_articles.out')
    eval_res = os.path.join(resdir, 'eval_articles.out')

    if not os.path.exists(resdir):
        logger.log('ERROR', 'resdir not found')
        return 1
    if not os.path.exists(top_docs):
        logger.log('ERROR', 'input file for evaluation not found')
        return 1

    # run trec_eval
    output = subprocess.check_output(
        [cfg.PATHS['trec_eval'], '-q', cfg.PATHS['rel_file'], top_docs])
    output = output.decode('ascii')
    with open(eval_res, 'a') as eval:
        eval.write(output)
    for line in output.splitlines():
        if re.search(r"map|bpref", line):
            if re.search(r"all", line):
                print(line)

    # run sample_eval
    output = subprocess.check_output(
        [cfg.PATHS['sample_eval'], '-q', cfg.PATHS['rel_file_s'], top_docs])
    output = output.decode('ascii')
    with open(eval_res, 'a') as eval:
        eval.write(output)
        logger.log('INFO', 'evaluation output saved [{}]'.format(eval_res),
                   printout=True)

    infAP_all = 0
    infNDCG_all = 0
    for line in output.splitlines():
        if re.search(r"infAP", line):
            if re.search(r"all", line):
                print(line)
                infAP_all = float(line.split()[2])
        if re.search(r"infNDCG", line):
            if re.search(r"all", line):
                print(line)
                infNDCG_all = float(line.split()[2])

    return infAP_all, infNDCG_all

