"""F: route-length scaling; 120 original instances only if their data is installed."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from statistics import mean,median
from .common import arguments, config, data_for, build, benchmark, save_csv, figure, comparison, ROOT
from befrg import read_montoya_xml
from .paper_values import REFERENCE


def main() -> None:
    args=arguments('F');cfg=config(args);q=cfg['experiments']['F']
    counts=q['route_customers'][:3 if args.quick else None]
    rows=[]
    if args.full:
        raw,src=data_for('tc2c320s38cf0',args,cfg,customers=320,stations=38)
        if max(counts)>len(raw.customers):
            raise ValueError('Original instance contains fewer than required customers; use synthetic for extra points')
    else:
        raw,src=data_for('tc2c320s38cf0',args,cfg,customers=max(counts),stations=q['stations'])
    for n in counts:
        p=build(raw,cfg,customers=n,stations=q['stations'])
        r=benchmark(p)
        rows.append({'customers':n,'route_nodes':len(p.route),'source':src,'provenance':'[ours-scaled-down]' if not args.full else '[ours-full]',**asdict(r)})
        print('F',n,r.rt_min,r.et_wall_s,flush=True)
    save_csv(args.output/'tables','exp_f',rows);save_csv(args.output/'tables','exp_f_paper_vs_ours',comparison('F',REFERENCE['F'],rows))
    figure(args.output/'figures','exp_f_scaling',[r['customers'] for r in rows],
           {'DPC wall sec':[r['et_wall_s'] for r in rows]},xlabel='Customers',ylabel='Wall time (sec)')
    # Corpus: never claim 120 instances if they are not present; all files are read explicitly.
    if args.full:
        xml_files=sorted((ROOT/'data/raw/montoya').rglob('tc*.xml'))
        corpus=[]
        for path in xml_files:
            item=read_montoya_xml(path)
            p=build(item,cfg)
            measured=benchmark(p)
            corpus.append({'instance':item.name,'class':item.name[:3],'customers':len(item.customers),
                           'stations':len(item.stations),'provenance':'[ours-full]',**asdict(measured)})
        save_csv(args.output/'tables','exp_f_full_corpus',corpus)
        print('F corpus count',len(corpus),'all120_present?',len(corpus)==120,flush=True)
    else:
        save_csv(args.output/'tables','exp_f_full_corpus_status',
                 [{'dataset':'Montoya','expected_instances':120,'present_instances':0,
                   'status':'[not run]: original XML files unavailable'}])

if __name__=='__main__':main()
