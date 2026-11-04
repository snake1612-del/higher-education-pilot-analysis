import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

p=argparse.ArgumentParser(description='Plot the pre-pilot interval using audited comparison exports.')
p.add_argument('comparisons', type=Path)
p.add_argument('names', type=Path)
p.add_argument('output', type=Path)
a=p.parse_args()
rows=json.loads(a.comparisons.read_text())
names=json.loads(a.names.read_text())
by_name={r['university']:r['short_name'] for r in names}
navy, muted, paper, teal, orange='#152D43','#566775','#FAFAF7','#007C83','#C46838'
fig, axs=plt.subplots(1,2,figsize=(12,5.1),facecolor=paper)
fig.subplots_adjust(left=.093,right=.97,top=.72,bottom=.23,wspace=.38)
fig.text(.035,.93,'Различия с предметным фоном были ещё до пилота',color=navy,weight='bold',fontsize=19)
fig.text(.035,.85,'Временное плацебо: 2021 → 2022, разность изменений вуза и его фона',color=muted,fontsize=12)
for ax,scope,side,key,order,title,bounds in [
 (axs[0],'whole','all','ege_fixed_gap',['БФУ','МАИ','МИСИС','МПГУ','Горный','ТГУ'],'Средний балл, баллы',(-5.9,1.5)),
 (axs[1],'cohort2023','linked','growth_gap_pp',['МАИ','МИСИС','МПГУ','ТГУ'],'Рост бюджетного зачисления, п.п.',(-12,16)),
]:
 selected=[r for r in rows if (r['scope'],r['side'],r['metric'],str(r['base_year']),str(r['end_year']))==(scope,side,'score','2021','2022')]
 assert len(selected)==len(order)
 values={by_name[r['university']]:float(r[key]) for r in selected}
 vs=[values[n] for n in order]
 ax.set_facecolor(paper); ax.set_axisbelow(True);ax.grid(axis='x',color='#DFE6E9')
 ax.axvline(0,color='#8799A5',lw=1)
 ax.barh(order,vs,color=[teal if v>=0 else orange for v in vs],height=.55)
 ax.invert_yaxis();ax.set_xlim(*bounds);ax.set_title(title,loc='left',color=navy,weight='bold',fontsize=12,pad=12)
 ax.tick_params(length=0,labelcolor=navy,pad=7);ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:g}'.replace('-','−')))
 for sp in ax.spines.values():sp.set_visible(False)
 for i,v in enumerate(vs):
  label=f'{v:+.2f}'.replace('.',',').replace('-','−')
  ax.text(v+(bounds[1]-bounds[0])*(.014 if v>=0 else -.014),i,label,va='center',ha='left' if v>=0 else 'right',color=navy,fontsize=10)
fig.text(.035,.105,'Слева: постоянные группы шести вузов. Справа: 16 групп, связанных с пилотом, у четырёх вузов.',color=muted,fontsize=10)
fig.text(.035,.06,'МКП НИУ ВШЭ, расчёты проекта. Один допилотный интервал; график показывает расхождения, а не статистическую значимость.',color=muted,fontsize=9)
fig.savefig(a.output,dpi=180,facecolor=paper)
