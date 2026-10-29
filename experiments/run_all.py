"""Run experiments sequentially with visible, deterministic CLI commands.

Default uses synthetic surrogates and is not a numerical paper reproduction.
`--full` demands original Montoya XML; Experiment H requires separate SUMO setup.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from .common import ROOT


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument('--quick',action='store_true')
    p.add_argument('--full',action='store_true')
    p.add_argument('--config',type=Path,default=ROOT/'configs/phase2.yaml')
    p.add_argument('--output',type=Path,default=ROOT/'results')
    args=p.parse_args()
    for letter in 'abcdefgh':
        if args.full and letter=='h':
            print('H real SUMO is not automated: use simulators/traci_controller.py; marked [not run]')
            continue
        command=[sys.executable,'-m',f'experiments.exp_{letter}',
                 '--config',str(args.config),'--output',str(args.output)]
        if args.quick:command.append('--quick')
        if args.full:command.append('--full')
        print('EXEC', ' '.join(command),flush=True)
        subprocess.run(command,cwd=ROOT,check=True)
    if not args.full:
        subprocess.run([sys.executable,'-m','experiments.summarize','--output',str(args.output)],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'-m','experiments.overview','--output',str(args.output)],cwd=ROOT,check=True)

if __name__=='__main__':main()
