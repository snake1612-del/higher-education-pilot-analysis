"""Local analysis of exact subject baskets. Outputs include restricted derivatives."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from independent_check import ROOT, YEARS, number, valid

MIN_DONORS = 5
HOLDOUT_LIMITS = np.array([2., 10.])  # points, 2021-based index points; diagnostic, not a test
METRICS = ('score', 'intake_index')


def simplex(v):
    ordered = np.sort(v)[::-1]
    cut = (np.cumsum(ordered) - 1) / np.arange(1, len(v) + 1)
    return np.maximum(v - cut[np.flatnonzero(ordered > cut)[-1]], 0.)


def fit(target, donors, ridge=1.):
    """Convex weights; ridge penalizes departure from uniform donor weights."""
    center = donors.mean(axis=0)
    d = donors - center
    n = len(d)
    uniform = np.full(n, 1/n)
    gram = d @ d.T + ridge * np.eye(n)
    linear = d @ (center - target) - ridge * uniform
    step = 1 / np.linalg.eigvalsh(gram)[-1]
    w = y = uniform
    t = 1.
    for _ in range(12000):
        z = simplex(y - step * (gram @ y + linear))
        if np.linalg.norm(z - simplex(z - step * (gram @ z + linear)), ord=1) < 1e-8:
            return z
        next_t = (1 + np.sqrt(1 + 4*t*t))/2
        y = z + (t-1)/next_t*(z-w)
        w, t = z, next_t
    raise RuntimeError('Synthetic weight solver did not converge')


def load(path):
    data = defaultdict(dict)
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = csv.reader(f, delimiter=';')
        next(rows)
        for row in rows:
            if len(row) != 19:
                raise ValueError('Expected the 19-column MKP budget export')
            u, g = (' '.join(row[i].split()) for i in (2, 0))
            if g in data[u]:
                raise ValueError('Duplicate university/group')
            data[u][g] = [tuple(number(row[k+i]) for k in (4,9,14)) for i in range(5)]
    return data


def eligible(groups, basket, years):
    return all(g in groups and all(valid(groups[g][i], 'score') for i in years) for g in basket)


def summarize(groups, basket, group_weights):
    cells = np.array([[(r[0], r[2]) for r in groups[g]] for g in basket], dtype=float)
    n, q = cells[:,:,0], cells[:,:,1]
    total = n.sum(axis=0)
    pre_shares = n[:,0] / total[0]
    k = len(basket)
    # Equal weight to each feature block: score (5-point scale), size (log 2),
    # and shares (20-point scale). Features are from 2021 only.
    features = np.r_[q[:,0] / (5*np.sqrt(k)), np.log2(total[0]), pre_shares / (.2*np.sqrt(k))]
    outcomes = np.stack([group_weights @ q, 100*total/total[0]], axis=-1)
    return features, outcomes


def contrast(actual, reference):
    """Difference in changes, with 2022 as the base; intake in growth p.p."""
    return np.column_stack([
        (actual[:,0]-actual[1,0]) - (reference[:,0]-reference[1,0]),
        100*(actual[:,1]/actual[1,1] - reference[:,1]/reference[1,1]),
    ])


def estimate(target, donors, features, outcomes, sensitivity=True):
    y = outcomes[target]
    x = np.stack([features[d] for d in donors])
    paths = np.stack([outcomes[d] for d in donors])
    w = fit(features[target], x)
    synthetic = np.einsum('d,dym->ym', w, paths)
    equal = paths.mean(axis=0)
    i = int(np.argmax(w))
    result = dict(actual=y.tolist(), synthetic=synthetic.tolist(), equal=equal.tolist(),
        synthetic_contrast=contrast(y, synthetic).tolist(), did=contrast(y, equal).tolist(),
        gap_2021=(y[0]-synthetic[0]).tolist(), gap_2022=(y[1]-synthetic[1]).tolist(),
        equal_gap_2022=(y[1]-equal[1]).tolist(),
        weights=dict(zip(donors,w.tolist())), top_weight=float(w[i]),
        effective_donors=float(1/(w@w)))
    if sensitivity:
        keep = np.arange(len(w)) != i
        reduced = np.einsum('d,dym->ym',fit(features[target],x[keep]),paths[keep])
        result['drop_top_contrast_2025'] = contrast(y, reduced)[-1].tolist()
    return result


def absolute_rank(actual, values):
    # Descriptive reference fraction, not a p-value or a confidence interval.
    return dict(placebos=len(values), at_least_as_large=sum(abs(v) >= abs(actual)-1e-9 for v in values))


def analyze(data, registry, identities):
    pilots = {r['university']:r['short_name'] for r in identities}
    result = []
    for u in registry['primary_universities']:
        basket = sorted({r['major_group'] for r in registry['links']
                         if r['university'] == u and r['scope'] == 'cohort2023'})
        if not basket or not eligible(data[u], basket, range(5)):
            raise ValueError('Incomplete focal basket')
        pre = sorted(d for d,g in data.items() if d not in pilots and eligible(g,basket,[0]))
        donors = [d for d in pre if eligible(data[d],basket,range(5))]
        entry = dict(university=pilots[u], groups=len(basket), eligible_2021=len(pre),
                     complete_donors=len(donors), status='insufficient_donors')
        result.append(entry)
        if len(donors) < MIN_DONORS:
            continue
        n = np.array([data[u][g][0][0] for g in basket])
        pairs = {d:summarize(data[d],basket,n/n.sum()) for d in [u,*donors]}
        features = {d:pair[0] for d,pair in pairs.items()}
        outcomes = {d:pair[1] for d,pair in pairs.items()}
        observed = estimate(u, donors, features, outcomes)
        placebos = [estimate(d,[j for j in donors if j!=d],features,outcomes,False) for d in donors]
        ranks = {}
        for j, metric in enumerate(METRICS):
            comparable = [p for p in placebos if abs(p['gap_2022'][j]) <= HOLDOUT_LIMITS[j]]
            ranks[metric] = dict(
                holdout_ok=bool(abs(observed['gap_2022'][j])<=HOLDOUT_LIMITS[j]),
                did=absolute_rank(observed['did'][-1][j],[p['did'][-1][j] for p in placebos]),
                synthetic=absolute_rank(observed['synthetic_contrast'][-1][j],
                    [p['synthetic_contrast'][-1][j] for p in comparable]),
            )
        entry.update(status='estimated', observed=observed, placebos=placebos, ranks=ranks)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mkp-csv', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    data = load(a.mkp_csv)
    registry, names = [json.loads((ROOT/'metadata'/f'{name}.json').read_text())
                       for name in ('scope_registry','university_names')]
    results = analyze(data, registry, names)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(dict(years=list(YEARS), holdout_limits=HOLDOUT_LIMITS.tolist(),
        min_donors=MIN_DONORS, cases=results),ensure_ascii=False,indent=2,allow_nan=False))
    for r in results:
        print(r['university'],r['eligible_2021'],r['complete_donors'],r['status'])
        if r['status']=='estimated':
            o=r['observed']
            print('  holdout synthetic/equal:',o['gap_2022'],o['equal_gap_2022'])
            print('  2025 DiD/synthetic/drop-top:',o['did'][-1],o['synthetic_contrast'][-1],o['drop_top_contrast_2025'])
            print('  maximum weight:',o['top_weight'],'placebo:',r['ranks'])


if __name__ == '__main__':
    main()
