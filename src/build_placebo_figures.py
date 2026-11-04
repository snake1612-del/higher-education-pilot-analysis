"""Render local diagnostic plots from the synthetic control and placebo run."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from placebo_synthetic import METRICS

PAPER, NAVY, TEAL, ORANGE, GRAY = '#FAFAF7','#152D43','#007C83','#C46838','#A8BBC5'
LABELS = ['Средний балл', 'Индекс зачисления (2021 = 100)']
CONTRAST_LABELS = ['Разность изменений, баллы', 'Разность темпов зачисления, п.п.']


def frame(cases, title, subtitle):
    fig, axes = plt.subplots(2,len(cases),figsize=(4.1*len(cases),6.7),squeeze=False,facecolor=PAPER)
    fig.subplots_adjust(left=.085,right=.97,bottom=.17,top=.78,wspace=.29,hspace=.5)
    fig.text(.07,.95,title,fontsize=19,weight='bold',color=NAVY,va='top')
    fig.text(.07,.89,subtitle,fontsize=10.7,color=NAVY,va='top')
    for row in axes:
        for ax, case in zip(row,cases):
            ax.set_title(case['university'],color=NAVY,weight='bold',loc='left')
            ax.set_facecolor(PAPER)
            ax.spines[['top','right']].set_visible(False)
            ax.tick_params(labelsize=8)
            ax.grid(axis='y',alpha=.2)
            ax.set_axisbelow(True)
    return fig, axes


def marker(color, label, style='-', marker=''):
    return Line2D([0],[0],color=color,ls=style,marker=marker,label=label)


def render(payload, out):
    cases=[c for c in payload['cases'] if c['status']=='estimated']
    years=payload['years']
    if not cases:
        raise ValueError('No estimated cases to plot')
    out.mkdir(parents=True,exist_ok=True)
    fig,axes=frame(cases,'Как аналоги совпадают с вузами до пилота',
        'Веса подобраны по 2021 году. Серая область — проверочный 2022 год; вертикальная линия — начало пилота.')
    for j,row in enumerate(axes):
        row[0].set_ylabel(LABELS[j])
        for ax,c in zip(row,cases):
            o=c['observed']
            ax.axvspan(2021.75,2022.25,color=GRAY,alpha=.2)
            ax.axvline(2023,color=GRAY,lw=1)
            for key,color,style in [('actual',NAVY,'-'),('synthetic',TEAL,'--'),('equal',GRAY,':')]:
                ax.plot(years,np.array(o[key])[:,j],color=color,ls=style,marker='o',ms=3)
            ax.set_xticks(years)
            gap=o['gap_2022'][j]
            ok=c['ranks'][METRICS[j]]['holdout_ok']
            ax.text(.99,1.04,f'Разрыв в 2022: {gap:+.2f}'.replace('.',','),
                    transform=ax.transAxes,ha='right',color=NAVY if ok else ORANGE,fontsize=8.7)
    fig.legend(handles=[marker(NAVY,'Факт'),marker(TEAL,'Синтетический аналог','--'),
        marker(GRAY,'Фон с равными весами',':')],loc='lower center',bbox_to_anchor=(.5,.056),ncol=3,frameon=False)
    fig.text(.07,.035,'МКП НИУ ВШЭ. ТГУ не показан: только два аналога с полным набором групп и лет.',fontsize=9,color=NAVY)
    fig.savefig(out/'synthetic_trajectories.png',dpi=160,facecolor=PAPER)
    plt.close(fig)

    fig,axes=frame(cases,'Насколько необычен разрыв к 2025 году?',
        'Точки — вузы без пилота. Для синтетического фона оставлены сравнения, прошедшие проверку на 2022 годе.')
    for j,row in enumerate(axes):
        row[0].set_ylabel(CONTRAST_LABELS[j])
        for ax,c in zip(row,cases):
            for y,key in [(0,'did'),(1,'synthetic_contrast')]:
                all_p=c['placebos']
                if y:
                    all_p=[p for p in all_p if abs(p['gap_2022'][j])<=payload['holdout_limits'][j]]
                values=sorted(p[key][-1][j] for p in all_p)
                jitter=((np.arange(len(values))*13 % 17)/16-.5)*.34
                ax.scatter(values,y+jitter,s=16,color=GRAY,alpha=.8,zorder=3)
                ok=not y or c['ranks'][METRICS[j]]['holdout_ok']
                ax.scatter(c['observed'][key][-1][j],y,s=65,marker='D',color=TEAL if ok else ORANGE,zorder=4)
            ax.axvline(0,color=GRAY,lw=1)
            ax.set_yticks([0,1],['Разн. изм.','Синт.'])
            ax.set_ylim(-.46,1.46)
            ax.set_xlabel(CONTRAST_LABELS[j],fontsize=8)
    for ax in axes.flat:
        ax.set_ylabel('')
    fig.legend(handles=[marker(GRAY,'Вуз без пилота','None','o'),marker(TEAL,'Пилотный вуз','None','D'),
        marker(ORANGE,'Синтетический аналог не прошёл проверку','None','D')],
        loc='lower center',bbox_to_anchor=(.5,.06),ncol=3,frameon=False,fontsize=9)
    fig.text(.07,.035,'МКП НИУ ВШЭ, 2022–2025. Это сравнение с плацебо, а не доверительные интервалы.',fontsize=9,color=NAVY)
    fig.savefig(out/'placebo_by_university.png',dpi=160,facecolor=PAPER)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    render(json.loads(a.results.read_text()),a.output)
