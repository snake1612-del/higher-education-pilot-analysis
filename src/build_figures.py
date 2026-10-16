"""Build the Russian and English README figures from local SQL exports.

No input data or calculated tables are uploaded. Defaults are relative to the
repository root. Run sql/10_export_chart_data.psql before this script.
"""
from pathlib import Path
import argparse
import csv
import math
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

NAVY, TEAL, ORANGE = '#152D43', '#007C83', '#C46838'
MUTED, GRID, PAPER, REF = '#566775', '#DFE6E9', '#FAFAF7', '#A8BBC5'
ORDER = ['БФУ', 'МАИ', 'МИСИС', 'МПГУ', 'Горный', 'ТГУ']
CORE = ['МАИ', 'МИСИС', 'МПГУ', 'ТГУ']
EN_NAMES = {'БФУ':'BFU','МАИ':'MAI','МИСИС':'MISIS','МПГУ':'MPGU',
            'Горный':'Mining Univ.','ТГУ':'TSU'}

def read_rows(path, fields, names):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not set(['university', *fields]).issubset(reader.fieldnames or []):
            raise ValueError(f'Missing required columns in {path.name}')
        rows = list(reader)
    if len(rows) != len(names) or {r['university'] for r in rows} != set(names):
        raise ValueError(f'Unexpected or duplicate universities in {path.name}')
    out = {}
    for row in rows:
        values = {k: float(row[k]) for k in fields}
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError(f'Missing or non-finite values in {path.name}')
        out[row['university']] = values
    return out

def label(value, lang, decimals=2, sign=False):
    value = 0.0 if abs(value) < 0.5 * 10**(-decimals) else value
    s = f'{value:+.{decimals}f}' if sign else f'{value:.{decimals}f}'
    return s.replace('.', ',') if lang == 'ru' else s

def style_axis(ax, lang, horizontal=False):
    ax.set_facecolor(PAPER)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis='both', length=0, labelcolor=NAVY, pad=8)
    ax.set_axisbelow(True)
    axis = ax.xaxis if horizontal else ax.yaxis
    axis.grid(True, color=GRID, linewidth=.8)
    axis.set_major_formatter(FuncFormatter(lambda x, _: label(x, lang, 0)))

def heading(fig, title, subtitle):
    fig.text(.035, .945, title, fontsize=17, color=NAVY, weight='bold', va='top')
    fig.text(.035, .865, subtitle, fontsize=11.5, color=MUTED, va='top')

def save(fig, output, name):
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / name, dpi=180, facecolor=PAPER,
                metadata={'Title': name.removesuffix('.png')})
    plt.close(fig)

def score_figure(rows, lang, output, meta):
    fig, ax = plt.subplots(figsize=(10.8, 4.8), facecolor=PAPER)
    fig.subplots_adjust(left=.16, right=.96, bottom=.17, top=.77)
    ru = lang == 'ru'
    heading(fig,
            'Общего повышения баллов относительно фона не выявлено' if ru else
            'No common increase in entrance scores relative to the benchmark',
            'Шесть вузов: постоянная панель групп. Изменения за 2022–2025, баллы' if ru else
            'Six universities: fixed group panel. Difference in changes, 2022–2025')
    values = [rows[u]['score_gap'] for u in ORDER]
    style_axis(ax, lang, horizontal=True)
    ax.barh(ORDER, values, color=[TEAL if v >= 0 else ORANGE for v in values], height=.58)
    ax.invert_yaxis()
    ax.set_yticks(range(len(ORDER)), ORDER if ru else [EN_NAMES[u] for u in ORDER])
    bounds(values, -5.25, 1.65, 'score')
    ax.set_xlim(-5.25, 1.65)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlabel('Разность изменений, баллы' if ru else 'Difference in changes, score points',
                  color=MUTED, labelpad=10)
    for i, v in enumerate(values):
        ax.text(v + (.10 if v >= 0 else -.10), i, label(v, lang, sign=True),
                va='center', ha='left' if v >= 0 else 'right', color=NAVY, weight='bold', fontsize=12)
    save(fig, output, 'scores.png')

def intake_figure(rows, lang, output, meta):
    fig, ax = plt.subplots(figsize=(10.8, 4.9), facecolor=PAPER)
    fig.subplots_adjust(left=.09, right=.97, bottom=.15, top=.76)
    ru = lang == 'ru'
    heading(fig,
            'Бюджетное зачисление менялось неодинаково' if ru else
            'State-funded enrolment followed different trajectories',
            f"Когорта 2023: {meta['intake']['groups']} связок, {meta['intake']['universities']} вуза. Изменение за 2022–2025, %" if ru else
            f"2023 cohort: {meta['intake']['groups']} university–group pairs, {meta['intake']['universities']} universities. Change in 2022–2025, %")
    style_axis(ax, lang)
    x = list(range(4)); width = .30
    values = [rows[u]['growth_pct'] for u in CORE]
    refs = [rows[u]['reference_growth_pct'] for u in CORE]
    bars1 = ax.bar([i-width/2 for i in x], values, width, color=TEAL,
                   label='Связанные группы' if ru else 'Linked groups')
    bars2 = ax.bar([i+width/2 for i in x], refs, width, color=REF,
                   label='Предметный фон' if ru else 'Subject benchmark')
    ax.axhline(0, color=MUTED, linewidth=1)
    ax.set_xticks(x, CORE if ru else [EN_NAMES[u] for u in CORE])
    bounds(values+refs, -12.5, 19.5, 'intake')
    ax.set_ylim(-12.5, 19.5)
    ax.set_ylabel('%', rotation=0, color=MUTED, labelpad=14)
    ax.legend(frameon=False, loc='upper left', ncols=2, fontsize=10.5, labelcolor=NAVY)
    for bars, vals in [(bars1, values), (bars2, refs)]:
        for rect, value in zip(bars, vals):
            ax.text(rect.get_x()+rect.get_width()/2,
                    value + (.55 if value >= 0 else -.6), label(value, lang, sign=True),
                    ha='center', va='bottom' if value >= 0 else 'top',
                    color=NAVY, fontsize=11, weight='bold')
    save(fig, output, 'intake.png')

def bvi_figure(rows, lang, output, meta):
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.0), facecolor=PAPER)
    fig.subplots_adjust(left=.07, right=.97, bottom=.17, top=.69, wspace=.34)
    ru = lang == 'ru'
    heading(fig,
            'Число БВИ выросло, а относительная динамика доли различалась' if ru else
            'BVI counts increased, while relative share changes were mixed',
            f"Отдельная полная подпанель: {meta['bvi']['groups']} связок, {meta['bvi']['universities']} вуза, 2022–2025" if ru else
            f"Separate complete subpanel: {meta['bvi']['groups']} pairs, {meta['bvi']['universities']} universities, 2022–2025")
    ax, gap = axes
    style_axis(ax, lang)
    xs = list(range(4)); width=.32
    a=[rows[u]['bvi0'] for u in CORE]; b=[rows[u]['bvi1'] for u in CORE]
    for shift, vals, color, year in [(-width/2,a,REF,'2022'),(width/2,b,TEAL,'2025')]:
        bars=ax.bar([i+shift for i in xs],vals,width,color=color,label=year)
        for bar,value in zip(bars,vals):
            ax.text(bar.get_x()+bar.get_width()/2,value+.8,str(int(value)),
                    ha='center',va='bottom',fontsize=11,weight='bold',color=NAVY)
    ax.set_xticks(xs,CORE if ru else [EN_NAMES[u] for u in CORE])
    bounds(a+b, 0, 46, 'BVI count')
    ax.set_ylim(0,46)
    ax.set_title('БВИ, человек' if ru else 'Entrants admitted without exams',
                 loc='left',fontsize=12,color=NAVY,pad=18)
    ax.legend(frameon=False,ncols=2,loc='upper left',fontsize=10,labelcolor=NAVY)
    style_axis(gap,lang,horizontal=True)
    values=[rows[u]['share_gap'] for u in CORE]
    gap.barh(range(4),values,color=[TEAL if v>=0 else ORANGE for v in values],height=.55)
    gap.set_yticks(range(4),CORE if ru else [EN_NAMES[u] for u in CORE])
    gap.invert_yaxis();gap.axvline(0,color=MUTED,linewidth=1)
    bounds(values, -5.3, 3.5, 'BVI share')
    gap.set_xlim(-5.3,3.5)
    gap.set_title('Изменение доли относительно фона, п.п.' if ru else
                  'Share change relative to benchmark, pp',loc='left',fontsize=12,color=NAVY,pad=18)
    for i,v in enumerate(values):
        gap.text(v+(.13 if v>=0 else -.13),i,label(v,lang,sign=True),
                 ha='left' if v>=0 else 'right',va='center',color=NAVY,fontsize=11,weight='bold')
    save(fig, output, 'bvi.png')

def bounds(values, lower, upper, name):
    if any(v < lower or v > upper for v in values):
        raise ValueError(f'{name}: data outside chart range; revise axes before publication')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path('outputs/chart_data'))
    parser.add_argument('--output-dir',type=Path,default=Path('assets'))
    args=parser.parse_args()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
                         'axes.labelsize':11,'axes.unicode_minus':True})
    meta=json.loads((args.data_dir/'panel_metadata.json').read_text())
    for key,expected in [('score',6),('intake',4),('bvi',4)]:
        if meta[key]['universities'] != expected or meta[key]['groups'] < expected:
            raise ValueError('Unexpected panel metadata: '+key)
    scores=read_rows(args.data_dir/'score_changes.csv',['score_gap','groups_used'],ORDER)
    intake=read_rows(args.data_dir/'intake_growth.csv',['growth_pct','reference_growth_pct','groups_used'],CORE)
    bvi=read_rows(args.data_dir/'bvi_changes.csv',['bvi0','bvi1','n0','n1','share_gap','groups_used'],CORE)
    for key,rows in [('score',scores),('intake',intake),('bvi',bvi)]:
        if any(r['groups_used']<=0 or not r['groups_used'].is_integer() for r in rows.values()) or sum(r['groups_used'] for r in rows.values()) != meta[key]['groups']:
            raise ValueError('Panel count does not match SQL export: '+key)
    for r in bvi.values():
        if not (r['n0']>0 and r['n1']>0 and 0<=r['bvi0']<=r['n0'] and 0<=r['bvi1']<=r['n1']):
            raise ValueError('Invalid BVI denominator or count')
    for lang in ['ru','en']:
        output=args.output_dir/lang
        score_figure(scores,lang,output,meta)
        intake_figure(intake,lang,output,meta)
        bvi_figure(bvi,lang,output,meta)
    print('Built three figures in Russian and English.')

if __name__=='__main__':
    main()
