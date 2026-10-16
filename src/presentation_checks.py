"""Independent checks of intake shares, internal contrasts and donor-count BVI.

Reads only the authorized MKP CSV and public registry; does not query SQL.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from independent_check import YEARS, number, valid, estimate

ROOT = Path(__file__).resolve().parents[1]


def donor_sensitivity(data, links, pools):
    rows,members = [],[]
    for minimum in (1,2,3,5):
        for university,groups in links.items():
            selected = sorted(g for g in groups
                if all(valid(data[university,g,y],'bvi') for y in YEARS)
                and len(pools[g,'bvi'])>=minimum)
            if not selected:
                continue
            for group in selected:
                members.append(dict(university=university,major_group=group,
                    min_controls=minimum,control_universities=len(pools[group,'bvi'])))
            result = estimate(data,university,selected,pools,'bvi',2022,2025)
            result.update(university=university,min_controls=minimum,
                share0=100*result['bvi0']/result['n0'],share1=100*result['bvi1']/result['n1'])
            rows.append(result)
    return rows,members


def calculate_extras(input_csv, comparisons):
    identities = json.loads((ROOT/'metadata/university_names.json').read_text())
    pilots = {r['university'] for r in identities}
    registry = json.loads((ROOT/'metadata/scope_registry.json').read_text())
    primary = set(registry['primary_universities'])
    links = defaultdict(set)
    for row in registry['links']:
        links[row['university'],row['scope']].add(row['major_group'])
    data,groups = {},defaultdict(set)
    with input_csv.open(encoding='utf-8-sig',newline='') as stream:
        rows = csv.reader(stream,delimiter=';')
        next(rows)
        for row in rows:
            u,g = ' '.join(row[2].split()),' '.join(row[0].split())
            groups[u].add(g)
            for i,year in enumerate(YEARS):
                data[u,g,year] = tuple(number(row[k+i]) for k in (4,9,14))
    pools = defaultdict(set)
    for u,gs in groups.items():
        if u in pilots:
            continue
        for group in gs:
            if all(valid(data[u,group,y],'bvi') for y in YEARS):
                pools[group,'bvi'].add(u)
    donor_rows,donor_members = donor_sensitivity(data,
        {u:links[u,'cohort2023'] for u in primary},pools)
    shares = []
    for university in primary:
        stable = {g for g in groups[university]
                  if all(valid(data[university,g,y],'intake') for y in YEARS)}
        linked = stable & links[university,'confirmed_eventual']
        for year in YEARS:
            total = sum(data[university,g,year][0] for g in stable)
            numerator = sum(data[university,g,year][0] for g in linked) if linked else None
            shares.append(dict(university=university,year=year,total_groups=len(stable),
                linked_groups=len(linked),total_admitted=total,linked_admitted=numerator,
                linked_share_pct=100*numerator/total if numerator is not None and total else None))
    internal = []
    for university in primary:
        for fixed in (False,True):
            def selected(side):
                return [r for r in comparisons if r['university']==university
                    and r['scope']=='cohort2023' and r['side']==side and r['metric']=='score'
                    and r['base_year']==2022 and r['end_year']==2025
                    and r['fixed_controls']==fixed]
            linked,other = selected('linked'),selected('other_observed')
            if not linked or not other:
                continue
            l,o = linked[0],other[0]
            internal.append(dict(university=university,
                weights='fixed_controls' if fixed else 'current_controls',
                linked_groups=l['groups_used'],other_groups=o['groups_used'],
                linked_gap=l['score_gap'],other_gap=o['score_gap'],
                internal_gap=l['score_gap']-o['score_gap']))
    return dict(linked_shares=shares,internal_contrasts=internal,
                bvi_donors=donor_rows,bvi_donor_members=donor_members)


def compare_extras(sql, python):
    specs = {
        'linked_shares':(('university','year'),('total_groups','linked_groups',
            'total_admitted','linked_admitted','linked_share_pct')),
        'internal_contrasts':(('university','weights'),('linked_groups','other_groups',
            'linked_gap','other_gap','internal_gap')),
        'bvi_donors':(('university','min_controls'),('groups_used','n0','n1','bvi0','bvi1',
            'share0','share1','share_gap_pp')),
        'bvi_donor_members':(('university','major_group','min_controls'),('control_universities',)),
    }
    result = {}
    for family,(keys,values) in specs.items():
        def indexed(rows):
            pairs = [(tuple(str(r[k]) for k in keys),r) for r in rows]
            if len(dict(pairs))!=len(pairs):
                raise AssertionError(('Duplicate presentation row',family))
            return dict(pairs)
        actual,expected = indexed(sql[family]),indexed(python[family])
        if actual.keys()!=expected.keys():
            raise AssertionError(('Presentation row membership differs',family))
        count = 0
        for key,row in expected.items():
            for column in values:
                a,b = row[column],actual[key][column]
                if a is None and b in ('',None):
                    continue
                if a is None or b in ('',None) or not math.isclose(a,float(b),abs_tol=1e-8,rel_tol=1e-10):
                    raise AssertionError((family,key,column,a,b))
                count += 1
        result[family] = dict(rows=len(actual),numeric_checks=count)
    return result
