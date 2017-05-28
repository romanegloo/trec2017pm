import re
import lxml.etree as et


def age_normalize(dom):
    """normalize age pattern into days (ex. 10 Years => 10 * 12 * 365)"""
    # age pattern
    r = r"([1-9][0-9]*) (Year|Years|Month|Months|Week|Weeks|Day|Days|Hour" \
        r"|Hours|Minute|Minutes)"
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
        m = re.match(r, min_age)
        min_age_norm = int(m.group(1)) * units[m.group(2)]

    max_age = dom.xpath("/doc/field[@name='eligibility-maximum_age']")[0].text
    max_age_norm = 200 * units['Years']
    if max_age != 'N/A' and max_age:
        m = re.match(r, max_age)
        max_age_norm = int(m.group(1)) * units[m.group(2)]

    fld_min = et.Element("field", name="eligibility-min_age_norm", type="float")
    fld_min.text = str(min_age_norm)
    fld_max = et.Element("field", name="eligibility-max_age_norm", type="float")
    fld_max.text = str(max_age_norm)

    dom.getroot().append(fld_min)
    dom.getroot().append(fld_max)

    return dom
