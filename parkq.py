"""ParkQ project-selection QUBO and classical route validation (Python stdlib)."""
import csv, itertools, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def load_rides(path=ROOT/'attractions.csv',demo=False):
    with open(path,newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    for r in rows:
        r['wait_minutes']=float(r['wait_minutes'])
        if r['ride_minutes']:
            r['ride_minutes']=float(r['ride_minutes'])
        elif demo:
            r['ride_minutes']=10.0 # EXPLICIT DEMO ASSUMPTION, NOT PARK DATA
        else: raise ValueError(f"Missing real ride duration for {r['ride_id']}; use demo=True only for testing")
    return rows

def load_walking(ids,path=ROOT/'walking_times_template.csv',demo=False):
    if demo:
        return {(a,b):(0.0 if a==b else 5.0) for a in ids for b in ids} # DEMO ONLY
    with open(path,newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    d={}
    for row in rows:
        a=row['from_id']
        for b in ids:
            if not row.get(b):raise ValueError(f'Missing walk time {a}->{b}')
            d[a,b]=float(row[b])
    if any((a,b) not in d for a in ids for b in ids):raise ValueError('Incomplete walking matrix')
    return d

def build_qubo(rides,preferences,budget,alpha=20.0,beta=0.1,penalty=None):
    """QUBO for attraction subset with integer-minute dwell budget.
    E=-sum(value_i*x_i)+lambda*(sum(cost_i*x_i)+slack-budget)^2.
    Walking is NOT included; exact route validation follows.
    Returns (variable_names, upper_triangular_Q, offset).
    """
    if int(budget)!=budget or budget<0:raise ValueError('Budget must be nonnegative integer minutes')
    budget=int(budget)
    ids=[r['ride_id'] for r in rides]
    costs=[int(math.ceil(r['wait_minutes']+r['ride_minutes'])) for r in rides]
    values=[alpha*float(preferences.get(id,3))-beta*r['wait_minutes'] for id,r in zip(ids,rides)]
    if penalty is None:penalty=sum(abs(v) for v in values)+1
    # bounded binary slack uses weights [1,2,...,remaining] to represent every integer 0..budget
    weights=[];remaining=budget;step=1
    while remaining:
        w=min(step,remaining);weights.append(w);remaining-=w;step*=2
    names=ids+[f'slack_{k}' for k in range(len(weights))]
    coeff=costs+weights
    linear=[-v for v in values]+[0.0]*len(weights)
    q={}
    for i,c in enumerate(coeff):q[i,i]=linear[i]+penalty*(c*c-2*budget*c)
    for i in range(len(coeff)):
        for j in range(i+1,len(coeff)):
            q[i,j]=2*penalty*coeff[i]*coeff[j]
    return names,q,penalty*budget*budget

def energy(bits,q,offset=0):
    return offset+sum(v*bits[i]*bits[j] for (i,j),v in q.items())

def project_candidates(rides,preferences,budget,top_k=12,alpha=20,beta=0.1):
    """Exact enumeration of subsets (NOT quantum QAOA); dwell-only budget."""
    ids=[r['ride_id'] for r in rides]; out=[]
    for bits in itertools.product((0,1),repeat=len(ids)):
        chosen=[r for r,b in zip(rides,bits) if b]
        dwell=sum(math.ceil(r['wait_minutes']+r['ride_minutes']) for r in chosen)
        if dwell>budget:continue
        score=sum(alpha*float(preferences.get(r['ride_id'],3))-beta*r['wait_minutes'] for r in chosen)
        out.append({'selected':[r['ride_id'] for r in chosen],'dwell_minutes':dwell,'score':round(score,3),'bitstring':''.join(map(str,bits))})
    return sorted(out,key=lambda z:(-z['score'],z['dwell_minutes']))[:top_k]

def best_route(selected,start,walking):
    """Held-Karp shortest open path; start may be an attraction ID; no return to start."""
    targets=[x for x in selected if x!=start]
    if not targets:return ([start] if start in selected else [],0.0)
    n=len(targets); dp={}
    for i,x in enumerate(targets):
        dp[1<<i,i]=(walking[start,x],(x,))
    for mask in range(1,1<<n):
        for j in range(n):
            if not mask&(1<<j) or (mask,j) not in dp:continue
            dist,path=dp[mask,j]
            for k in range(n):
                if mask&(1<<k):continue
                key=(mask|(1<<k),k);new=(dist+walking[targets[j],targets[k]],path+(targets[k],))
                if key not in dp or new[0]<dp[key][0]:dp[key]=new
    dist,path=min((dp[(1<<n)-1,j] for j in range(n)),key=lambda p:p[0])
    return list(path),dist

def validate_candidates(candidates,rides,start,walking,budget):
    byid={r['ride_id']:r for r in rides}; results=[]
    for c in candidates:
        route,walk=best_route(c['selected'],start,walking)
        wait=sum(byid[i]['wait_minutes'] for i in c['selected'])
        play=sum(byid[i]['ride_minutes'] for i in c['selected'])
        total=wait+play+walk
        results.append({**c,'route':route,'walk_minutes':round(walk,2),'wait_minutes':round(wait,2),'play_minutes':round(play,2),'total_minutes':round(total,2),'feasible':total<=budget})
    return results

def to_qiskit_quadratic_program(names,q,offset):
    """Member 4 integration: pip install qiskit-optimization."""
    from qiskit_optimization import QuadraticProgram
    qp=QuadraticProgram('ParkQ_project_selection')
    for name in names:qp.binary_var(name=name)
    linear={names[i]:v for (i,j),v in q.items() if i==j}
    quadratic={(names[i],names[j]):v for (i,j),v in q.items() if i!=j}
    qp.minimize(constant=offset,linear=linear,quadratic=quadratic)
    return qp

if __name__=='__main__':
    rides=load_rides(demo=True); prefs={r['ride_id']:3 for r in rides}
    names,q,offset=build_qubo(rides,prefs,240)
    walking=load_walking(list(prefs),demo=True)
    candidates=project_candidates(rides,prefs,240,top_k=30)
    results=validate_candidates(candidates,rides,'R_1',walking,240)
    print('QUBO variables:',len(names),'nonzero terms:',len(q))
    print('Top feasible routes (DEMO WALK + DEMO RIDE TIMES):')
    for r in [x for x in results if x['feasible']][:5]:print(r)
