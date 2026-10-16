"""Run only in an EMPTY disposable database: no tables are deleted.

Checks changing control composition, absent background, known zero intake,
and the final-panel fail-fast guard. Uses synthetic observations only.
"""
import argparse
import csv
import io
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn',required=True)
    parser.add_argument('--psql',default='psql')
    args = parser.parse_args()
    base = [args.psql,'-X','-q','-v','ON_ERROR_STOP=1','--dbname',args.dsn]
    def run(*opts, ok=True):
        result = subprocess.run(base+list(opts),text=True,capture_output=True)
        if ok and result.returncode:
            raise RuntimeError(result.stderr)
        return result
    def query(sql):
        return list(csv.DictReader(io.StringIO(run('--csv','-c',sql).stdout)))
    if query("SELECT to_regclass('research_raw.mkp_budget') IS NOT NULL AS exists")[0]['exists']=='t':
        raise ValueError('Requires an empty disposable database')
    run('-f',str(ROOT/'sql/00_schema.sql'))
    pilot = query("SELECT university FROM research.pilot_universities WHERE short_name='МАИ'")[0]['university']
    def quote(x):
        return "'"+str(x).replace("'","''")+"'"
    def row(u,g,ns,qs):
        return '('+','.join(quote(x) for x in [g,'synthetic',u,'synthetic',*ns,*([0]*5),*qs])+')'
    rows = [row(pilot,'A',[100]*5,[80]*5),
            row('high','A',[90,90,10,10,10],[90]*5),
            row('low','A',[10,10,90,90,90],[60]*5),
            row(pilot,'orphan',[100]*5,[70]*5),
            row(pilot,'zero',[0,0,20,20,20],['']*5),
            row('zero_control','zero',[100]*5,[50]*5)]
    run('-c','INSERT INTO research_raw.mkp_budget VALUES '+','.join(rows))
    run('-c',"INSERT INTO research.scope_links VALUES "+','.join(
        '('+','.join(map(quote,[pilot,g,'cohort2023','synthetic test']))+')'
        for g in ('A','orphan','zero')))
    for name in ('01_prepare_data.sql','04_fixed_panels.sql','11_audit_sensitivity.sql'):
        run('-f',str(ROOT/'sql'/name))
    old = query("SELECT ege_fixed_gap FROM research.comparison_changes WHERE scope='cohort2023' AND side='linked' AND metric='score' AND base_year=2022 AND end_year=2025")[0]
    fixed = query("SELECT score_gap FROM research.double_fixed_score_changes WHERE scope='cohort2023' AND side='linked' AND base_year=2022 AND end_year=2025")[0]
    assert abs(float(old['ege_fixed_gap'])-24)<1e-10
    assert abs(float(fixed['score_gap']))<1e-10
    orphan = query("SELECT status FROM research.selection_flow WHERE major_group='orphan' AND metric='score' AND base_year=2022")[0]
    assert orphan['status']=='no_complete_controls'
    intake = query("SELECT groups_used,n0,n1 FROM research.comparison_changes WHERE scope='cohort2023' AND side='linked' AND metric='intake' AND base_year=2022 AND end_year=2025")[0]
    assert tuple(float(intake[k]) for k in ('groups_used','n0','n1'))==(2,100,120)
    guard = run('-f',str(ROOT/'sql/12_assert_final_panels.sql'),ok=False)
    assert guard.returncode and 'Панель score' in guard.stderr
    print('PASS: composition / missing background / zero intake / panel guard')


if __name__=='__main__':
    main()
