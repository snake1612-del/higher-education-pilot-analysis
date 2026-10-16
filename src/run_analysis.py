"""Run the study locally in a fresh PostgreSQL database, stop on any failure.

Usage: python src/run_analysis.py --mkp PATH --dsn 'dbname=... user=...'
Passwords belong in .pgpass, not command arguments or source files.
"""
import argparse
import csv
import io
import json
import math
import subprocess
import sys
from pathlib import Path
from prepare_inputs import prepare
from independent_check import calculate

ROOT = Path(__file__).resolve().parents[1]


def execute(args):
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    private = output/'inputs'
    prepare(args.mkp, args.mev, private)
    base = [args.psql,'-X','-q','-v','ON_ERROR_STOP=1','--dbname',args.dsn]
    def run(*options):
        result = subprocess.run(base+list(options),text=True,capture_output=True,cwd=ROOT)
        if result.returncode:
            # Do not print a DSN containing connection credentials.
            raise RuntimeError(result.stderr)
        return result.stdout
    def query(sql):
        return list(csv.DictReader(io.StringIO(run('--csv','-c',sql))))
    def save(name, rows):
        (output/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    def load(table,path,delimiter):
        quoted = str(path.resolve()).replace("'","''")
        run('-c',f"\\copy {table} FROM '{quoted}' WITH (FORMAT CSV, HEADER TRUE, DELIMITER '{delimiter}', ENCODING 'UTF8')")
    def file(name):
        text = run('-f',str(ROOT/'sql'/name))
        (output/(name+'.log')).write_text(text)
    if query("SELECT to_regclass('research_raw.mkp_budget') IS NOT NULL AS exists")[0]['exists']=='t':
        raise ValueError('Project tables already exist. Use a fresh database; no automatic deletion is performed.')
    file('00_schema.sql')
    load('research_raw.mkp_budget',private/'mkp_budget.csv',';')
    load('research.scope_links',private/'scope_links.csv',',')
    for name in ['01_prepare_data.sql','02_quality_checks.sql','04_fixed_panels.sql',
                 '03_exploratory_comparison.sql','05_main_comparisons.sql',
                 '06_linked_intake_share.sql','07_bvi.sql','08_baseline_sensitivity.sql',
                 '11_audit_sensitivity.sql','12_assert_final_panels.sql']:
        file(name)
    if args.mev:
        file('09_mev_context.sql')
        load('research_raw.mev_selected',private/'mev_selected.csv',';')
        load('research.mev_crosswalk',private/'mev_crosswalk.csv',',')
        file('09_mev_context.sql')
        save('mev_context',query('SELECT p.short_name,m.* FROM research.mev_context m JOIN research.mev_crosswalk x ON x.mev_id=m.id JOIN research.pilot_universities p ON p.university=x.university WHERE m.id_parent IS NULL AND m.report_year IN (2021,2022) ORDER BY p.short_name,m.report_year'))
    tables = {
        'comparisons':'SELECT * FROM research.comparison_changes',
        'double_fixed':'SELECT * FROM research.double_fixed_score_changes',
        'bvi_thresholds':'SELECT * FROM research.bvi_threshold_changes',
        'selection_flow':'SELECT * FROM research.selection_flow',
        'panel_coverage':'SELECT * FROM research.panel_coverage',
        'panel_members':'SELECT * FROM research.final_panel_members',
    }
    sql = {name:query(command) for name,command in tables.items()}
    for name,rows in sql.items():
        save(name,rows)
    python = calculate(private/'mkp_budget.csv')
    save('independent_python',python)
    def key(r, metric=None, fixed=False, threshold=0):
        return (r['university'],r['scope'],metric or r.get('metric'),
                int(r['base_year']),int(r['end_year']),fixed,threshold)
    lookup = {}
    for r in sql['comparisons']:
        if r['side'] not in ('all','linked'):
            continue
        lookup[key(r)] = r
    for r in sql['double_fixed']:
        if r['side'] in ('all','linked'):
            lookup[key(r,'score',True)] = r
    for r in sql['bvi_thresholds']:
        lookup[key(r,'bvi',False,int(r['min_bvi']))] = r
    checked = 0
    for r in python:
        k = key(r,fixed=r['fixed_controls'],threshold=r['min_bvi'])
        target = lookup.pop(k)
        names = ['groups_used']
        if r['fixed_controls']:
            names += ['score_gap']
        elif r['metric']=='bvi' and r['scope']!='whole':
            names += ['n0','n1','bvi0','bvi1','share_gap_pp']
        else:
            names += ['n0','n1','growth_pct','growth_gap_pp']
            if r['metric']=='score':
                target = dict(target,score_gap=target['ege_fixed_gap'])
                names += ['score_gap']
            elif r['metric']=='bvi':
                target = dict(target,share_gap_pp=target['bvi_share_gap_pp'])
                names += ['bvi0','bvi1','share_gap_pp']
        for name in names:
            a,b = r[name],target[name]
            if a is None and b in ('',None):
                continue
            if a is None or b in ('',None) or not math.isclose(a,float(b),abs_tol=1e-8,rel_tol=1e-10):
                raise AssertionError((k,name,a,b))
            checked += 1
    if lookup:
        raise AssertionError('SQL has unmatched comparison rows')
    chart_dir = output/'chart_data'
    chart_dir.mkdir(exist_ok=True)
    export = (ROOT/'sql/10_export_chart_data.psql').read_text()
    export = export.replace('outputs/chart_data',str(chart_dir).replace("'","''"))
    export_path = output/'export.psql'
    export_path.write_text(export)
    run('-f',str(export_path))
    counts = {}
    for label,scope,metric,side in [('score','whole','score','all'),
                                   ('intake','cohort2023','score','linked'),
                                   ('bvi','cohort2023','bvi','linked')]:
        rows = [r for r in sql['comparisons'] if r['scope']==scope and r['metric']==metric
                and r['side']==side and r['base_year']=='2022' and r['end_year']=='2025']
        counts[label] = dict(groups=sum(int(r['groups_used']) for r in rows),universities=len(rows))
    (chart_dir/'panel_metadata.json').write_text(json.dumps(counts,indent=2))
    validation = dict(status='pass',independent_rows=len(python),numeric_checks=checked,
                      panel_assertions='16 score / 8 BVI / 4 universities',
                      input_sha256=json.loads((private/'input_hashes.json').read_text()),
                      engine=run('-t','-A','-c','SHOW server_version').strip())
    save('validation',validation)
    print(json.dumps(validation,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mkp',type=Path,required=True)
    parser.add_argument('--mev',type=Path)
    parser.add_argument('--dsn',required=True)
    parser.add_argument('--psql',default='psql')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs')
    execute(parser.parse_args())
