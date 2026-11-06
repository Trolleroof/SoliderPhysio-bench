"""Versioned, reproducible Elo summaries of matched campaign outcomes.

Raw metrics remain authoritative. Ratings summarize this opponent/case pool only.
"""
import itertools
import math
import random


VERSION = 'campaign-elo-v1'


def _valid_metric(run, metric):
    result = run['final']
    if result.get('valid') is not True:
        return None
    value = result.get(metric)
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('valid runs require finite nonnegative '+metric)
    if result.get('code_execution_verified') is not True:
        raise ValueError('ranked runs require executable-code verification')
    return value


def leaderboard(runs, metric='mae_bpm', *, seed=0, initial=1000.0, k=32.0, tie_tolerance=1e-9):
    if metric not in ('mae_bpm', 'interval_score_90'):
        raise ValueError('unsupported rating metric')
    if not runs:
        raise ValueError('matched runs required')
    if type(seed) is not int or not all(type(x) in (int,float) and math.isfinite(x) for x in (initial,k,tie_tolerance)) or k <= 0 or tie_tolerance < 0:
        raise ValueError('invalid rating configuration')
    cells={}
    for run in runs:
        name=run.get('competitor')
        case=run.get('case')
        if not isinstance(name,str) or not name or type(case) is not int:
            raise ValueError('competitor names and integer case IDs required')
        key=(case,name)
        if key in cells:
            raise ValueError('duplicate competitor/case; use explicit repetition IDs')
        cells[key]=_valid_metric(run,metric)
    names=sorted({name for _,name in cells})
    cases=sorted({case for case,_ in cells})
    if len(names)<2:
        raise ValueError('at least two competitors required')
    if set(cells) != set(itertools.product(cases,names)):
        raise ValueError('all competitors must run the same complete case batch; failures must be explicit')
    ratings={name:float(initial) for name in names}
    counts={name:{'wins':0,'draws':0,'losses':0,'skipped_both_invalid':0,
                  'valid_cases':sum(cells[(case,name)] is not None for case in cases)} for name in names}
    schedule=[(case,a,b) for case in cases for a,b in itertools.combinations(names,2)]
    random.Random(seed).shuffle(schedule)
    matches=[]
    for case,a,b in schedule:
        av,bv=cells[(case,a)],cells[(case,b)]
        if av is None and bv is None:
            counts[a]['skipped_both_invalid']+=1
            counts[b]['skipped_both_invalid']+=1
            matches.append({'case':case,'a':a,'b':b,'outcome':'skipped_both_invalid'})
            continue
        outcome=(0.0 if av is None else 1.0 if bv is None else
                 .5 if abs(av-bv)<=tie_tolerance else 1.0 if av<bv else 0.0)
        expected=1/(1+10**(max(-300,min(300,(ratings[b]-ratings[a])/400))))
        delta=k*(outcome-expected)
        ratings[a]+=delta
        ratings[b]-=delta
        for name,points in ((a,outcome),(b,1-outcome)):
            counts[name]['wins' if points==1 else 'losses' if points==0 else 'draws']+=1
        matches.append({'case':case,'a':a,'b':b,'score_a':outcome,
                        'metric_a':av,'metric_b':bv,'rating_delta_a':delta})
    entries=[]
    for name in names:
        games=sum(counts[name][field] for field in ('wins','draws','losses'))
        entries.append({'competitor':name,'elo':ratings[name],'games':games,
                        'eligible':counts[name]['valid_cases']>0 and games>0,**counts[name]})
    entries.sort(key=lambda row:(not row['eligible'],-row['elo'],row['competitor']))
    for row in entries:
        row['rank']=(1+sum(other['eligible'] and other['elo']>row['elo']+1e-9 for other in entries)
                     if row['eligible'] else None)
    return {'version':VERSION,'metric':metric,'direction':'lower error wins',
            'configuration':{'initial':initial,'k':k,'scale':400,'match_order_seed':seed,
                             'absolute_tie_tolerance':tie_tolerance},
            'scope':{'case_ids':cases,'competitors':names,'unit':'one complete campaign',
                     'status':'provisional; pool-dependent and match-order-dependent; no confidence interval estimated'},
            'entries':entries,'matches':matches}


def campaign_ratings(runs):
    return {'prediction':leaderboard(runs,'mae_bpm'),
            'uncertainty':leaderboard(runs,'interval_score_90')}
