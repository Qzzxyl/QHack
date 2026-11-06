'use strict';
// app.py enables backend mode when an optimizer module is configured.
const USE_DEMO = typeof window === 'undefined' ||
  document.querySelector('meta[name="universal-data-mode"]')?.content !== 'backend';
// All operational values below are fixtures, not official park data.
const RIDES = [
  {id:'R_1',photo:'/ride-1.png',name:'Despicable Me Minion Mayhem',english:'Despicable Me Minion Mayhem',zone:'minions',tags:['family','immersive'],queue:35,duration:12,rating:4.7,reviews:1286,icon:'🍌',color:'#f3e9bd'},
  {id:'R_2',photo:'/ride-2.png',name:'Loop-Dee Doop-Dee',english:'Loop-Dee Doop-Dee',zone:'minions',tags:['family','thrill'],queue:20,duration:5,rating:4.3,reviews:824,icon:'🎢',color:'#e5eac7'},
  {id:'R_3',photo:'/ride-3.png',name:'Harry Potter and the Forbidden Journey',english:'Harry Potter and the Forbidden Journey',zone:'harry',tags:['magic','immersive','thrill'],queue:60,duration:15,rating:4.9,reviews:2361,icon:'🏰',color:'#e0e2ee'},
  {id:'R_4',photo:'/ride-4.png',name:'Flight of the Hippogriff',english:'Flight of the Hippogriff',zone:'harry',tags:['magic','family'],queue:30,duration:5,rating:4.5,reviews:956,icon:'🪽',color:'#e8e4d6'},
  {id:'R_5',photo:'/ride-5.jpg',name:'Jurassic World Adventure',english:'Jurassic World Adventure',zone:'jurassic',tags:['thrill','immersive'],queue:50,duration:15,rating:4.8,reviews:1832,icon:'🦖',color:'#dbe7d2'},
  {id:'R_6',photo:'/ride-6.jpg',name:'Jurassic Flyers',english:'Jurassic Flyers',zone:'jurassic',tags:['thrill','family'],queue:40,duration:8,rating:4.6,reviews:1105,icon:'🌿',color:'#e2ebdf'},
  {id:'R_7',photo:'/ride-7.png',name:'Transformer: Battle for the AllSpark',english:'Transformer: Battle for the AllSpark',zone:'transformers',tags:['thrill','immersive'],queue:45,duration:12,rating:4.8,reviews:1724,icon:'🤖',color:'#dce6e7'},
  {id:'R_8',photo:'/ride-8.jpg',name:'Lanterns of Legendary Legends',english:'Lanterns of Legendary Legends',zone:'kungfu',tags:['family','immersive'],queue:15,duration:8,rating:4.4,reviews:647,icon:'🏮',color:'#f0dfd0'}
];
const ZONES = {entrance:[0,0],minions:[2,1],harry:[5,4],jurassic:[3,5],transformers:[1,4],kungfu:[5,1]};
const $ = id => document.getElementById(id);
let filter = 'all', latest = null, revision = 0;
const escapeHTML = text => String(text).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const durationText = n => n >= 60 ? `${Math.floor(n/60)} hr${n%60 ? ` ${n%60} min` : ''}` : `${n} min`;

let catalog = new Map();
let catalogRequest;

function rideMetrics(ride) {
  if (!USE_DEMO) return catalog.get(ride.id) ?? {};
  return {
    rating: ride.rating,
    wait_minutes: ride.queue,
    origin_distance_m: distanceMeters($('location').value, ride.id)
  };
}

async function fetchJSON(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'The service request failed.');
  return body;
}

async function loadCatalog() {
  if (USE_DEMO) return;
  catalogRequest?.abort();
  const controller = new AbortController();
  catalogRequest = controller;
  const status = $('catalog-status');
  catalog = new Map();
  renderRides();
  status.hidden = false;
  status.textContent = 'Loading attraction information…';
  const query = new URLSearchParams({ current_location: $('location').value });
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const body = await fetchJSON(`/api/attractions?${query}`, { signal: controller.signal });
    if (catalogRequest !== controller) return;
    if (!Array.isArray(body.attractions)) throw new Error('Invalid attraction response.');
    const metrics = new Map();
    for (const row of body.attractions) {
      if (!RIDES.some(ride => ride.id === row?.ride_id) || metrics.has(row.ride_id)) {
        throw new Error('Unknown or duplicate attraction ID.');
      }
      for (const key of ['rating', 'wait_minutes', 'origin_distance_m']) {
        const value = row[key];
        if (value !== null && (!Number.isFinite(value) || value < 0 || (key === 'rating' && value > 5))) {
          throw new Error('Invalid attraction metrics.');
        }
      }
      metrics.set(row.ride_id, row);
    }
    catalog = metrics;
    status.hidden = true;
    renderRides();
  } catch (error) {
    if (catalogRequest === controller) {
      status.textContent = error.name === 'AbortError' ? 'Attraction data request timed out.' : error.message;
    }
  } finally {
    clearTimeout(timeout);
  }
}

function renderRides() {
  const rides = RIDES.filter(ride => filter === 'all' || ride.tags.includes(filter));
  const sortKey = { rating: 'rating', queue: 'wait_minutes', distance: 'origin_distance_m' }[$('sort').value];
  if (sortKey) {
    const order = sortKey === 'rating' ? -1 : 1;
    const sortValue = ride => rideMetrics(ride)[sortKey] ?? (order === -1 ? -1 : Infinity);
    rides.sort((a, b) => order * (sortValue(a) - sortValue(b)));
  }
  $('ride-list').innerHTML = rides.map(ride => {
    const { rating, wait_minutes: wait, origin_distance_m: distance } = rideMetrics(ride);
    const ratingLabel = rating == null ? 'Rating unavailable' : `★ ${rating.toFixed(1)} / 5`;
    const waitLabel = wait == null ? 'Wait unavailable' : `◷ Wait ${wait} min`;
    const distanceLabel = distance == null ? 'Distance unavailable' : `↝ ${formatDistance(distance)} from you${USE_DEMO ? ' (demo)' : ''}`;
    return `<article class="ride-card" role="button" tabindex="0" aria-pressed="false">
      <div class="ride-photo"><img src="${ride.photo}" alt="" decoding="async">
        <div class="ride-caption"><span class="ride-code">${ride.id}</span><h3 class="ride-title">${ride.name}</h3>
        <span class="ride-score">${ratingLabel}${USE_DEMO ? ' <small>Demo rating</small>' : ''}</span></div>
      </div><div class="ride-info"><div class="ride-meta"><span class="queue">${waitLabel}</span>
      <span class="distance">${distanceLabel}</span></div></div>
    </article>`;
  }).join('');
}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{
  filter=button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});
  renderRides();
}));
$('sort').addEventListener('change',renderRides);
$('location').addEventListener('change', () => {
  if (USE_DEMO) renderRides();
  else loadCatalog();
});
$('planner-form').addEventListener('input',()=>{revision++;if(latest)$('result-tag').textContent='Settings changed · Regenerate route';});

function readRequest(){
  return {current_location:$('location').value,preferences:[...document.querySelectorAll('[name=preference]:checked')].map(e=>e.value),total_time_minutes:Number($('duration').value)};
}
// Fictional coordinates: 150 m per grid unit plus a 150 m area offset.
function distanceMeters(a,b){
  if (a === b) return 0;
  const zone = id => RIDES.find(ride => ride.id === id)?.zone ?? id;
  const x=ZONES[zone(a)],y=ZONES[zone(b)];return Math.round((Math.hypot(x[0]-y[0],x[1]-y[1])*150+150)/10)*10;}
function formatDistance(m){return m>=1000 ? `${(m/1000).toFixed(2)} km` : `${Math.round(m)} m`;}
function walking(a,b){return Math.ceil(distanceMeters(a,b)/70);}

// UI-only greedy fixture generator. It is NOT QAOA or a globally optimal route.
function demoResult(request){
  let candidates=[...RIDES],steps=[],location=request.current_location,elapsed=0;
  while(candidates.length){
    const possible=candidates.filter(r=>elapsed+walking(location,r.id)+r.queue+r.duration<=request.total_time_minutes);
    if(!possible.length)break;
    possible.sort((a,b)=>{
      const score=r=>(1+3*r.tags.filter(t=>request.preferences.includes(t)).length)/(walking(location,r.id)+r.queue+r.duration);
      return score(b)-score(a);
    });
    const ride=possible[0],walk=walking(location,ride.id);
    steps.push({ride_id:ride.id,walk_minutes:walk,queue_minutes:ride.queue,ride_minutes:ride.duration,walk_distance_m:distanceMeters(location,ride.id),origin_distance_m:distanceMeters(request.current_location,ride.id)});
    elapsed+=walk+ride.queue+ride.duration;location=ride.id;
    candidates=candidates.filter(r=>r.id!==ride.id);
  }
  return {steps};
}
// Normalize and enforce the shared response contract before display.
function validateResult(result,request){
  if(!result||!Array.isArray(result.steps)||result.steps.length>RIDES.length)throw Error('Invalid route response: a valid steps array is required.');
  const seen=new Set();let time=0;
  for(const step of result.steps){
    if(!step||!RIDES.some(r=>r.id===step.ride_id)||seen.has(step.ride_id))throw Error('The route contains an unknown or repeated attraction.');
    seen.add(step.ride_id);
    for(const key of ['walk_minutes','queue_minutes','ride_minutes']){
      if(typeof step[key]!=='number'||!Number.isFinite(step[key])||step[key]<0)throw Error('The route contains invalid times.');
    }
    for(const key of ['walk_distance_m','origin_distance_m']){
      if(step[key]!==null && (typeof step[key]!=='number'||!Number.isFinite(step[key])||step[key]<0))
        throw Error('The route contains invalid distances.');
    }
    time+=step.walk_minutes+step.queue_minutes+step.ride_minutes;
  }
  if(time>request.total_time_minutes)throw Error('The route exceeds your available time. Check the backend response.');
  return result;
}
function renderResult(result,request,isDemo){
  const steps=result.steps;
  const usingSampleData = isDemo || result.solver_mode === 'demo';
  $('result-tag').textContent=usingSampleData?'Demo route · Not QAOA':'Optimized itinerary';
  if(!steps.length){$('route-content').innerHTML='<div class="empty-state"><div class="empty-icon">◷</div><h3>No route fits these settings.</h3><p>Try adding more time, then plan again.</p></div>';return;}
  const sum=key=>steps.reduce((n,s)=>n+s[key],0),walk=sum('walk_minutes'),queue=sum('queue_minutes'),ride=sum('ride_minutes'),distance=steps.every(s=>s.walk_distance_m!==null)?sum('walk_distance_m'):null,total=walk+queue+ride;
  let elapsed=0;
  const timeline = steps.map((step, index) => {
    const attraction = RIDES.find(ride => ride.id === step.ride_id);
    const arrival = elapsed + step.walk_minutes;
    elapsed = arrival + step.queue_minutes + step.ride_minutes;
    const previousDistance = index === 0 ? '' :
      `<br>From previous attraction: ${step.walk_distance_m===null?'Distance unavailable':formatDistance(step.walk_distance_m)}`;
    return `<div class="step">
      <span class="step-number">${String(index + 1).padStart(2, '0')}</span>
      <div class="step-detail">
        <div class="step-top">
          <h3>${attraction.name}</h3>
          <div class="step-window">
            <span>Arrival ~ finish · from trip start</span>
            <time>${arrival} min ~ ${elapsed} min</time>
          </div>
        </div>
        <p>Walk ${step.walk_minutes} min · Wait ${step.queue_minutes} min · Ride ${step.ride_minutes} min</p>
        <p>From your starting location: ${step.origin_distance_m===null?'Distance unavailable':formatDistance(step.origin_distance_m)}${previousDistance}</p>
      </div>
    </div>`;
  }).join('');
  $('route-content').innerHTML=`<div class="summary"><div class="metric"><strong>${steps.length} <small>rides</small></strong><small>Experiences</small></div><div class="metric"><strong>${total} <small>min</small></strong><small>Total duration</small></div><div class="metric"><strong>${request.total_time_minutes-total} <small>min</small></strong><small>Time to spare</small></div></div><p class="breakdown">◷ Walk ${walk} min + Wait ${queue} min + Ride ${ride} min<br>Times are relative to the start of your visit · Meals, breaks and return walk excluded</p><div class="timeline">${timeline}</div><div class="result-actions"><span>${'Itinerary returned by the connected QAOA optimization service.'}</span><button id="download" type="button">↓ Export route</button></div>`;
  $('download').addEventListener('click',()=>{
    const data={mode:isDemo?'demo':'backend',request,...result,total_time_minutes:total,total_walk_distance_m:distance};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='universal-itinerary.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}
$('planner-form').addEventListener('submit',async event=>{
  event.preventDefault();$('form-error').textContent='';
  const request=readRequest(),isDemo=USE_DEMO,submittedRevision=revision;
  if (!$('duration').reportValidity()) return;
  if(!request.preferences.length){$('form-error').textContent='Please select at least one preference.';return;}
  const button=$('optimize');button.disabled=true;button.textContent='Planning your route…';$('results').setAttribute('aria-busy','true');
  $('result-tag').textContent='Planning';$('route-content').innerHTML='<div class="loading"><div class="spinner"></div>Putting your adventure together…</div>';
  try{
    let result;
    if(isDemo){await new Promise(resolve=>setTimeout(resolve,450));result=demoResult(request);}
    else{
      if(location.protocol==='file:')throw Error('To connect an optimizer, open the app through the Python server.');
      const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),120000);
      try{result = await fetchJSON('/api/optimize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), signal: controller.signal });}finally{clearTimeout(timeout);}
    }
    validateResult(result,request);latest={result,request};renderResult(result,request,isDemo);
    location.hash = 'results';
    if(submittedRevision!==revision)$('result-tag').textContent='Settings changed · Regenerate route';
  }catch(error){latest=null;$('result-tag').textContent='Planning failed';$('route-content').innerHTML=`<p class="result-message">${escapeHTML(error.name==='AbortError'?'The request timed out. Please try again.':error.message)}</p>`;}
  finally{button.disabled=false;button.innerHTML='✦ Optimize · Plan my route <span>→</span>';$('results').setAttribute('aria-busy','false');}
});
renderRides();
if (!USE_DEMO) loadCatalog();

// Each stage uses the same form and route state while replacing the visible panel.
if (typeof window !== 'undefined') {
  const stageIds = ['entrance', 'attractions', 'planner', 'results'];

  function showStage(moveFocus) {
    const requested = window.location.hash.slice(1);
    const active = stageIds.includes(requested) ? requested : 'entrance';
    for (const id of stageIds) {
      $(id).hidden = id !== active;
      const link = document.querySelector(`nav a[href="#${id}"]`);
      if (id === active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    if (moveFocus) {
      $(active).focus({ preventScroll: true });
      window.scrollTo(0, 0);
    }
  }

  window.addEventListener('hashchange', () => showStage(true));
  showStage(false);


}

if (typeof window !== 'undefined') {
  const track = $('ride-list');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let pauseUntil = 0;
  let mouseOverTrack = false;

  function selectRide(card) {
    const selected = card?.getAttribute('aria-pressed') === 'true';
    for (const item of track.querySelectorAll('.ride-card')) {
      item.setAttribute('aria-pressed', String(item === card && !selected));
    }
    pauseUntil = card && !selected ? Date.now() + 6500 : 0;
    if (card && !selected) {
      track.scrollTo({
        left: track.scrollLeft + card.getBoundingClientRect().left - track.getBoundingClientRect().left,
        behavior: 'instant'
      });
    }
  }

  function moveRides(direction) {
    const card = track.querySelector('.ride-card');
    if (!card) return;
    const limit = track.scrollWidth - track.clientWidth;
    if (limit <= 1) return;
    const stride = card.getBoundingClientRect().width + parseFloat(getComputedStyle(track).columnGap);
    const position = track.scrollLeft;
    const target = direction > 0 && position >= limit - 2 ? 0
      : direction < 0 && position <= 2 ? limit
      : position + direction * stride;
    track.scrollTo({ left: target, behavior: reduced.matches ? 'instant' : 'smooth' });
  }

  track.addEventListener('click', event => {
    const card = event.target.closest('.ride-card');
    if (card) selectRide(card);
  });
  track.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const card = event.target.closest('.ride-card');
    if (!card) return;
    event.preventDefault();
    selectRide(card);
  });
  track.addEventListener('pointerenter', event => {
    if (event.pointerType !== 'mouse') return;
    mouseOverTrack = true;
    track.scrollTo({ left: track.scrollLeft, behavior: 'instant' });
  });
  track.addEventListener('pointerleave', event => {
    if (event.pointerType !== 'mouse') return;
    mouseOverTrack = false;
    selectRide(null);
  });
  track.addEventListener('pointerdown', () => { pauseUntil = Date.now() + 6500; });
  $('rides-prev').addEventListener('click', () => {
    selectRide(null);
    pauseUntil = Date.now() + 6500;
    moveRides(-1);
  });
  $('rides-next').addEventListener('click', () => {
    selectRide(null);
    pauseUntil = Date.now() + 6500;
    moveRides(1);
  });
  window.setInterval(() => {
    if (mouseOverTrack || reduced.matches || $('attractions').hidden || document.hidden || Date.now() < pauseUntil) return;
    selectRide(null);
    moveRides(1);
  }, 1500);
}

if (typeof window !== 'undefined') {
  const entrance = $('entrance');
  entrance.addEventListener('pointermove', event => {
    if (event.pointerType !== 'mouse') return;
    const bounds = entrance.getBoundingClientRect();
    entrance.style.setProperty('--glow-x', `${event.clientX - bounds.left}px`);
    entrance.style.setProperty('--glow-y', `${event.clientY - bounds.top}px`);
  });
  entrance.addEventListener('pointerleave', () => {
    entrance.style.removeProperty('--glow-x');
    entrance.style.removeProperty('--glow-y');
  });
}

if (typeof window !== 'undefined') {
  const introduction = $('visit-intro');
  introduction.addEventListener('toggle', () => {
    if (!introduction.open) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    introduction.scrollIntoView({ block: 'start', behavior: reducedMotion ? 'instant' : 'smooth' });
  });
}
