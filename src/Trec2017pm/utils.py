import os
import re
import sys
import lxml.etree as et
from nltk import sent_tokenize

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import config as cfg
from Trec2017pm.logger import Logger
from pymetamap import MetaMap
from umls_api import UMLS_api

logger = Logger()  # singleton
mm = MetaMap.get_instance('/opt/public_mm/bin/metamap16')


def age_normalize(dom):
    """normalize age pattern into days (ex. 10 Years => 10 * 12 * 365)"""
    # age pattern
    pattern = r"([1-9][0-9]*) (Year|Years|Month|Months|Week|Weeks" \
              r"Day|Days|Hour|Hours|Minute|Minutes)"
    units = {
        'Year': 12 * 365,
        'Years': 12 * 365,
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


def parse_topics(path, qexp_atoms=False):
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
    queries = []
    gene_types = ['amplification', 'fusion', 'transcript', 'inactivating',
                  'loss', 'deletion']
    age_groups_str = ['Infant, Newborn', 'Infant', 'Child, Preschool', 'Child',
                      'Adolescent', 'Adult', 'Middle Aged', 'Aged',
                      'Aged, 80 and over']
    age_groups_num = [0, 1/12, 2, 5, 12, 18, 44, 64, 79]
    assert len(age_groups_str) == len(age_groups_num), \
        "age_groups are not in sync"

    if not os.path.isfile(path):
        logger.log('ERROR', 'topic file cannot be found', die=True,
                   printout=True)

    doc = et.parse(path)
    # preprocessing
    for t in doc.iterfind('.//topic'):
        q = {}
        q_terms = []
        """ 
        <disease>
        - expand with the preferred disease name in mesh terms
        """
        # get CUI of the given disease name
        logger.log('INFO', '- disease/ name: {}'.format(t[0].text))
        if qexp_atoms:
        # if False:
            with UMLS_api.Client() as client:
                cuis = client.get_cuis(t[0].text)
                atoms = client.get_atoms(cuis['results'][0]['ui'])
                atom_names = ['"' + a['name'] + '"' for a in atoms]
                atom_names_cc = ' OR '.join(atom_names)
                q_terms.append("({})".format(atom_names_cc))
                logger.log('INFO',
                           "{} expands [{}]"
                           "".format(t[0].text, atom_names_cc))
        else:
            q_terms.append(t[0].text)

        """
        <gene>
        - parse "gene_id [(variant)|variant type]"
        """
        genes = t[1].text.split(',')
        for gene in genes:
            gene = gene.strip().lower()
            pattern_found = False

            m = re.match(r"(.+)\((\w+)\)", gene)
            # ex) braf (v600e)
            if not pattern_found and m:
                gene_name = m.group(1).strip()
                variation = m.group(2)
                pattern_found = True
            m = re.match(r"([\w\s-]+)({})".format('|'.join(gene_types)), gene)
            if not pattern_found and m:
                # ignore variation type for now
                gene_name = m.group(1).strip()
                variation = m.group(2)
                pattern_found = True
            # otherwise
            if not pattern_found:
                gene_name = gene
                variation = None
            logger.log('INFO', '- gene/ name: {} variation: {}'.
                       format(gene_name, variation))
            if qexp_atoms:
                with UMLS_api.Client() as client:
                    # get atoms of gene
                    cuis = client.get_cuis(gene_name)
                    atoms = client.get_atoms(cuis['results'][0]['ui'])
                    if atoms is None:
                        q_terms.append(gene_name)
                    else:
                        atom_names = ['"' + a['name'] + '"' for a in atoms]
                        atom_names_cc = ' OR '.join(atom_names)
                        q_terms.append("({})^2".format(atom_names_cc))
                        logger.log('INFO',
                                   "{} expands [{}]"
                                   "".format(gene_name, atom_names_cc))

                    # get atoms of gene+variation
                    if variation is not None:
                        cuis = client.get_cuis(gene_name + ' ' + variation)
                        atoms = client.get_atoms(cuis['results'][0]['ui'])
                        if atoms is None:
                            q_terms.append(variation)
                        else:
                            atom_names = ['"' + a['name'] + '"' for a in atoms]
                            atom_names_cc = ' OR '.join(atom_names)
                            q_terms.append("({})^3".format(atom_names_cc))
                            logger.log('INFO',
                                       "{} expands [{}]"
                                       "".format(variation, atom_names_cc))

            else:
                q_terms.append(gene_name)
                if variation is not None:
                    q_terms.append(variation)


        """
        <demographic>
        - extract age and sex
        - age maps to MeSH terms
        """
        pattern = r"(\d+)-year-old (male|female)"
        m = re.match(pattern, t[2].text)
        if m:
            age = int(m.group(1))
            sex = m.group(2)
            logger.log('INFO', '- demographic/ age: {} sex: {}'.
                       format(age, sex))
            if age is not None:
                # find corresponding age group (in str)
                g_idx = -1
                for i, g in enumerate(age_groups_num):
                    if age > g:
                        g_idx = i
                    else:
                        break
                q_terms.append('MeshHeading:"{}"'.format(age_groups_str[g_idx]))
            if sex == 'male':
                q_terms.append('MeshHeading:Male')
            elif sex == 'female':
                q_terms.append('MeshHeading:Female')

        q['query'] = ' '.join(q_terms)
        # other configurations
        queries.append(q)
    return queries


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


