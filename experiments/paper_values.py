"""Selected reference values manually transcribed from Mandal et al. Tables 2–7.

All observations here are [paper], NOT measurements from our code.
The paper contains internal unit/denominator contradictions; preserve the
printed table labels and explicitly flag ambiguities in docs/phase2_report.md.
"""
from __future__ import annotations

REFERENCE: dict[str,list[dict[str,object]]] = {
 'A':[{'setting':f'R={n},gamma=40,Gamma=40','metric':'RT_MILP','value':m,'unit':'hr','reference':'Table 2'} for n,m in zip((50,70,90,100,150),(6.09,8.48,11.76,13.47,20.50))] +
     [{'setting':f'R={n},gamma=40,Gamma=40','metric':'RT_BEFRG','value':d,'unit':'hr','reference':'Table 2'} for n,d in zip((50,70,90,100,150),(6.64,9.87,13.89,15.74,23.49))],
 'B':[{'setting':f'R={n}','metric':'ET_no_memo','value':e,'unit':'table says sec; text says ms','reference':'Table 4a'} for n,e in zip((5,6,7,8,9,10),(8,72,786,8435,100205,1220341))],
 'C':[{'setting':f'R={n}','metric':'RT','value':r,'unit':'min','reference':'Table 4b'} for n,r in zip((15,20,25,30,35,40,45,50),(137,181,234,291,351,415,479,531))],
 'D':[{'setting':f'JC={n}','metric':'RT','value':r,'unit':'min','reference':'Table 5a'} for n,r in zip((15,20,25,30,35),(5761,5508,5145,4871,4692))],
 'E':[{'setting':f'gamma={n}','metric':'RT','value':r,'unit':'hr','reference':'Table 6a'} for n,r in zip((2,4,8,16),(84.17,80.62,78.48,77.75))],
 'F':[{'setting':f'R={n}','metric':'ET','value':e,'unit':'sec','reference':'Table 6b'} for n,e in zip((320,640,960,1280,1600),(5,10,15,17,19))],
 'G':[{'setting':f'R={n}','metric':'RT_DPC','value':r,'unit':'min','reference':'Table 7a'} for n,r in zip((40,80,120,160,200,240,280,320),(415,878,1306,1875,2377,2982,3687,4602))] +
     [{'setting':f'R={n}','metric':'RT_FC','value':r,'unit':'min','reference':'Table 7a'} for n,r in zip((40,80,120,160,200,240,280,320),(455,968,1442,2028,2623,3343,4111,5132))],
 'H':[{'setting':f'SF_V={n}','metric':'RT','value':r,'unit':'min (table), seconds (text)','reference':'Table 5b'} for n,r in zip((296,286,226,156,106,36,26,16),(6021,6020,6017,6018,6019,6094,6096,6020))] +
     [{'setting':f'Amsterdam_V={n}','metric':'RT','value':r,'unit':'min (table)','reference':'Table 7b'} for n,r in zip((500,1000,1500,2000,2500,3000),(2558,2730,2995,3567,4559,4320))],
}
