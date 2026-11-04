"""Render README figures using only aggregate pilot contrasts and placebo counts."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

PAPER, INK, TEAL, GRAY = '#FAFAF7', '#152D43', '#007C83', '#A8BBC5'
TRANSLATIONS = {
    'ru': ('Опережение по зачислению зависит от вуза',
           'Разность темпов роста бюджетного зачисления за 2022–2025 годы, п.п.',
           'Фон с равными весами', 'Синтетический фон',
           'Плацебо с таким же или большим разрывом', 'По абсолютной величине, среди прошедших проверку на 2022 годе',
           'У ТГУ два аналога с полными данными: оценка не рассчитана. МКП НИУ ВШЭ, расчёты автора.'),
    'en': ('Relative enrolment growth differs across universities',
           'Difference in state-funded enrolment growth rates, 2022–2025, percentage points',
           'Equal-weight benchmark', 'Synthetic benchmark',
           'Placebos with a gap at least as large', 'In absolute terms, among cases that passed the 2022 holdout check',
           'TSU had only two complete matches, so it is not estimated. Source: HSE MKP, author calculations.'),
}
NAMES = {'МАИ': 'MAI', 'МПГУ': 'MPGU', 'МИСИС': 'MISIS'}


def render(cases, path, lang):
    title, subtitle, equal, synthetic, right_title, right_subtitle, note = TRANSLATIONS[lang]
    rows = [c for c in cases if c['status'] == 'estimated']
    labels = [c['university'] if lang == 'ru' else NAMES[c['university']] for c in rows]
    left = np.array([[c['observed'][m][-1][1] for m in ('did','synthetic_contrast')] for c in rows])
    counts = [(c['ranks']['intake_index']['synthetic']['at_least_as_large'],
               c['ranks']['intake_index']['synthetic']['placebos']) for c in rows]
    if not all(c['ranks']['intake_index']['holdout_ok'] for c in rows) or any(n==0 for _,n in counts):
        raise ValueError('README summary requires a passed holdout and a nonempty placebo pool')
    fig, (a,b) = plt.subplots(1,2,figsize=(11.6,4.05),facecolor=PAPER,
                              gridspec_kw={'width_ratios': [1.16,1]})
    fig.subplots_adjust(left=.105,right=.965,bottom=.21,top=.70,wspace=.29)
    fig.text(.035,.945,title,color=INK,fontsize=18,weight='bold',va='top')
    fig.text(.035,.852,subtitle,color=INK,fontsize=10.2,va='top')
    for ax in (a,b):
        ax.set_facecolor(PAPER)
        ax.spines[:].set_visible(False)
        ax.tick_params(length=0,labelcolor=INK,pad=6)
        ax.set_ylim(len(rows)-.55,-.55)
    pos=np.arange(len(rows))
    a.set_yticks(pos,labels)
    a.axvline(0,color='#7D929F',linewidth=.9)
    for i,(color,label) in enumerate(((GRAY,equal),(TEAL,synthetic))):
        yy=pos+(-.145 if i==0 else .145)
        values=left[:,i]
        a.barh(yy,values,height=.22,color=color,label=label)
        for x,y in zip(values,yy):
            amount=f'{x:+.2f}'.replace('-','−')
            if lang=='ru':
                amount=amount.replace('.',',')
            a.text(x+(.65 if x>=0 else -.65),y,amount,va='center',
                   ha='left' if x>=0 else 'right',fontsize=9,color=INK)
    a.set_xlim(min(-17,left.min()-4),max(17,left.max()+4))
    a.set_xticks([])
    a.legend(loc='upper center',bbox_to_anchor=(.52,-.015),ncol=2,frameon=False,fontsize=8.4)
    b.set_yticks([])
    b.set_xticks([])
    b.text(0,1.09,right_title,transform=b.transAxes,fontsize=10.7,color=INK,weight='bold')
    b.text(0,1.012,right_subtitle,transform=b.transAxes,fontsize=8.2,color=INK)
    b.barh(pos,np.ones(len(rows)),height=.24,color='#E0E7E9')
    b.barh(pos,[k/n for k,n in counts],height=.24,color=TEAL)
    b.set_xlim(0,1.17)
    for y,(k,n) in zip(pos,counts):
        b.text(1.025,y,f'{k}/{n}',va='center',fontsize=9.5,color=INK)
    fig.text(.035,.043,note,fontsize=8.4,color=INK)
    path.parent.mkdir(parents=True,exist_ok=True)
    with matplotlib.rc_context({'svg.fonttype':'none','svg.hashsalt':'ivo-placebo-2026'}):
        fig.savefig(path,facecolor=PAPER,metadata={'Date':None} if path.suffix=='.svg' else None)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',required=True,type=Path)
    p.add_argument('--assets',required=True,type=Path)
    args=p.parse_args()
    cases=json.loads(args.results.read_text())['cases']
    for lang in TRANSLATIONS:
        render(cases,args.assets/lang/'placebo_summary.svg',lang)
