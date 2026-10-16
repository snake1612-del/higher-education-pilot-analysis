"""Independent standard-library calculation from the local 19-column MKP CSV.

Does not query PostgreSQL or consume its results to construct the estimates.
The SQL comparison uses independently assembled panels and Python arithmetic.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEARS = range(2021, 2026)


def number(value):
    value = ''.join(str('' if value is None else value).split()).replace(',', '.')
    if value.lower() in ('','-','—','–','н/д','н.д.','nan','na','n/a','null'):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite number')
    return result


def valid(row, metric):
    n, b, q = row
    if n is None or n < 0:
        return False
    if metric == 'intake':
        return True
    return n > 0 and (q is not None if metric == 'score'
                     else b is not None and 0 <= b <= n)


def estimate(data, university, groups, pools, metric, base, end, fixed_controls=False):
    """One fixed set, same groups at both endpoints, own metric's denominators."""
    def annual(year):
        n = b = qsum = ref_n = ref_b = ref_q = weight = 0.
        for group in groups:
            current = data[university,group,year]
            initial = data[university,group,base]
            control = pools[group,metric]
            cn0 = sum(data[u,group,base][0] for u in control)
            cn = sum(data[u,group,year][0] for u in control)
            n += current[0]
            if metric == 'bvi':
                b += current[1]
                ref_b += initial[0]*sum(data[u,group,year][1] for u in control)/cn0
            if metric == 'score':
                qsum += initial[0]*current[2]
                cq = sum(data[u,group,base if fixed_controls else year][0]
                         *data[u,group,year][2] for u in control)
                ref_q += initial[0]*cq/(cn0 if fixed_controls else cn)
            ref_n += initial[0]*cn/cn0
            weight += initial[0]
        return dict(n=n,b=b,q=qsum/weight if metric=='score' else None,
                    rn=ref_n,rb=ref_b,rq=ref_q/weight if metric=='score' else None)
    a, z = annual(base), annual(end)
    growth = 100*(z['n']/a['n']-1) if a['n'] else None
    rg = 100*(z['rn']/a['rn']-1) if a['rn'] else None
    return dict(groups_used=len(groups),n0=a['n'],n1=z['n'],growth_pct=growth,
                growth_gap_pp=growth-rg if growth is not None and rg is not None else None,
                score_gap=(z['q']-a['q'])-(z['rq']-a['rq']) if metric=='score' else None,
                bvi0=a['b'] if metric=='bvi' else None,bvi1=z['b'] if metric=='bvi' else None,
                share_gap_pp=100*((z['b']/z['n']-a['b']/a['n'])
                 -(z['rb']/z['rn']-a['rb']/a['rn'])) if metric=='bvi' else None)


def calculate(input_csv, registry=None):
    registry = registry or json.loads((ROOT/'metadata/scope_registry.json').read_text())
    identities = json.loads((ROOT/'metadata/university_names.json').read_text())
    pilots = {r['university']:r['short_name'] for r in identities}
    data = {}
    groups_by_u = defaultdict(set)
    with input_csv.open(encoding='utf-8-sig',newline='') as stream:
        rows = csv.reader(stream, delimiter=';')
        next(rows)
        for row in rows:
            if len(row)!=19:
                raise ValueError('MKP must contain exactly 19 columns')
            group, university = ' '.join(row[0].split()), ' '.join(row[2].split())
            groups_by_u[university].add(group)
            for i,year in enumerate(YEARS):
                key = university,group,year
                if key in data:
                    raise ValueError('Duplicate university/group/year')
                data[key] = tuple(number(row[offset+i]) for offset in (4,9,14))
    stable = {metric:{(u,g) for u,gs in groups_by_u.items() for g in gs
                      if all(valid(data[u,g,y],metric) for y in YEARS)}
              for metric in ('score','bvi','intake')}
    pools = defaultdict(set)
    for metric, pairs in stable.items():
        for u,g in pairs:
            if u not in pilots:
                pools[g,metric].add(u)
    links = defaultdict(set)
    for row in registry['links']:
        links[row['university'],row['scope']].add(row['major_group'])
    results = []
    for u in pilots:
        for scope in ('whole','cohort2023','confirmed_eventual'):
            if scope != 'whole' and u not in registry['primary_universities']:
                continue
            for metric in ('score','bvi','intake'):
                candidates = groups_by_u[u] if scope=='whole' else links[u,scope]
                for base in (2021,2022):
                    gs = sorted(g for g in candidates if (u,g) in stable[metric]
                                and pools[g,metric]
                                and sum(data[c,g,base][0] for c in pools[g,metric])>0)
                    if not gs:
                        continue
                    for fixed in ((False,True) if metric=='score' else (False,)):
                        thresholds = (0,5,10,20) if metric=='bvi' and scope!='whole' else (0,)
                        for threshold in thresholds:
                            selected = [g for g in gs if metric!='bvi' or data[u,g,base][1]>=threshold]
                            if not selected:
                                continue
                            for end in range(base+1,2026):
                                result = estimate(data,u,selected,pools,metric,base,end,fixed)
                                result.update(university=u,scope=scope,metric=metric,base_year=base,
                                              end_year=end,fixed_controls=fixed,min_bvi=threshold)
                                results.append(result)
    return results


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(calculate(args.input),ensure_ascii=False,indent=2))
