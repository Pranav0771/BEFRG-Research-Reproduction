"""Readable paper-vs-surrogate overview with N/A numeric differences."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from .common import ROOT,save_csv


def get(file: str, base: Path):
    with (base / 'tables' / file).open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results')
    base=parser.parse_args().output
    a=get('exp_a.csv',base); b=get('exp_b.csv',base); c=get('exp_c.csv',base); d=get('exp_d.csv',base)
    e=get('exp_e.csv',base); f=get('exp_f.csv',base); g=get('exp_g.csv',base); h=get('exp_h_substitute.csv',base)
    v=get('phase2_verdicts.csv',base)
    paper=[
       ('A','Table 2: gap ~8–15% at Gamma=40',f"DP/discrete MILP agreement in {sum(r['DP_MILP_same_value']=='True' for r in a)}/{len(a)} cases; sparse example gap 33.6%"),
       ('B','Table 4a: nonmemo ET to 1,220,341 (unit disputed)','No-memo 100,000-call budget exceeded for 5–7 customers'),
       ('C','Table 4b: 137–531 minutes','Our synthetic route RT %.3f–%.3f min'%(float(c[0]['rt_min']),float(c[-1]['rt_min']))),
       ('D','Table 5a: RT 5761→4692 minutes','Our nested-station RT %.3f→%.3f min'%(float(d[0]['rt_min']),float(d[-1]['rt_min']))),
       ('E','Table 6a: RT 84.17→77.75 hours','Our gamma sweep RT %.3f→%.3f min'%(float(e[0]['rt_min']),float(e[-1]['rt_min']))),
       ('F','Table 6b: 320–1600 points, 5–19s; corpus 47s','Our 20–320 customers ET %.3f→%.3f sec'%(float(f[0]['et_wall_s']),float(f[-1]['et_wall_s']))),
       ('G','Table 7a: at |R|=320 FC 5132, DPC 4602 min','Our %s customers FC %.3f, DPC %.3f min (validation status in CSV)'%(g[-1].get('customers', '?'),float(g[-1]['FC_RT_min']),float(g[-1]['DPC_RT_min']))),
       ('H','Tables 5b / 7b: SF + Amsterdam network traffic','Our substitute V=%s: static %.3f, snapshot %.3f min'%(h[-1].get('vehicles','?'),float(h[-1]['static_realized_min']),float(h[-1]['snapshot_realized_min']))),
    ]
    rows=[]
    for (exp,paper_claim,ours),verdict in zip(paper,v):
        rows.append({'experiment':exp,'paper_reference':'[paper] '+paper_claim,
                     'ours_observed':'[ours-scaled-down] '+ours,
                     'absolute_difference':'N/A: different instance and experiment sizes',
                     'relative_difference_pct':'N/A: different instance and experiment sizes',
                     'qualitative_trend_agreement':verdict['trend_agreement'],
                     'strict_reproducibility':'Could not test exact source conditions',
                     'trend_verdict':verdict['verdict']})
    save_csv(base/'tables','phase2_paper_ours_overview',rows)

if __name__=='__main__':main()
