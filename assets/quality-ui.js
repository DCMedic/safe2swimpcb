(()=>{
  const ready=fn=>document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fn,{once:true}):fn();
  const PATHS={
    '/':'/data/current_flag.json','/destin/':'/data/destin/current_flag.json','/okaloosa-island/':'/data/okaloosa-island/current_flag.json',
    '/navarre-beach/':'/data/navarre-beach/current_flag.json','/pensacola-beach/':'/data/pensacola-beach/current_flag.json','/south-walton/':'/data/south-walton/current_flag.json',
    '/cape-san-blas/':'/data/cape-san-blas/current_flag.json','/st-george-island/':'/data/franklin-county/current_flag.json','/anna-maria-island/':'/data/anna-maria-island/current_flag.json',
    '/siesta-key/':'/data/siesta-key/current_flag.json','/venice/':'/data/venice/current_flag.json','/sanibel/':'/data/sanibel/current_flag.json',
    '/fort-myers-beach/':'/data/fort-myers-beach/current_flag.json','/naples/':'/data/naples/current_flag.json','/marco-island/':'/data/marco-island/current_flag.json'
  };
  const norm=()=>{let p=location.pathname||'/';if(!p.endsWith('/'))p+='/';return p.replace(/\/+/g,'/')};
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const LABELS={
    corroborated:['High confidence','Local authority and fresh Mote/VisitBeaches Ambassador observations agree.','good'],
    partial_corroboration:['Good confidence','Primary warning flag agrees across sources; an overlay or secondary detail differs.','warn'],
    primary_only:['Verified primary source','Current status is based on the local authority; no fresh Ambassador flag is available.','neutral'],
    source_disagreement:['Source disagreement','Fresh sources disagree. The local authority remains primary while the discrepancy is retained for review.','alert'],
    conflict:['VisitBeaches conflict','Fresh Ambassador observations conflict, so they are not used to synthesize a regional flag.','alert'],
    visitbeaches_gap_filled:['Ambassador verified','A fresh, internally consistent Mote/VisitBeaches Ambassador report filled a missing or stale local-source gap.','good'],
    visitbeaches_gap_fill:['Ambassador verified','A fresh, internally consistent Mote/VisitBeaches Ambassador report fills the current gap.','good'],
    visitbeaches_newer_than_stale_primary:['Newer Ambassador observation','The local-source observation is stale and a newer consistent Ambassador report is available.','warn']
  };
  async function addConfidence(){
    const url=PATHS[norm()];if(!url)return;
    try{
      const r=await fetch(url,{cache:'no-store'});if(!r.ok)return;const c=await r.json();
      const state=c.multi_source_confidence||c.visitbeaches_evidence?.state;if(!state)return;
      const spec=LABELS[state]||['Source verified',String(state).replaceAll('_',' '),'neutral'];
      const card=document.querySelector('.flag-card-wide,.flag-card');if(!card||card.querySelector('.ktg-confidence'))return;
      const box=document.createElement('div');box.className=`ktg-confidence ktg-confidence-${spec[2]}`;box.setAttribute('role','status');
      box.innerHTML=`<div class="ktg-confidence-title"><span class="ktg-confidence-dot" aria-hidden="true"></span>${esc(spec[0])}</div><div class="ktg-confidence-copy">${esc(spec[1])}</div>`;
      const freshness=card.querySelector('#flagFreshness,#statusFreshness,.flag-status,.status');
      if(freshness)freshness.insertAdjacentElement('afterend',box);else card.appendChild(box);
    }catch(_){/* Confidence is additive; core safety status remains usable. */}
  }
  function improveTouchTargets(){
    document.querySelectorAll('a.btn,button,.location-link,.tab,.menu-toggle').forEach(el=>el.classList.add('ktg-touch-target'));
  }
  function improveDenseMetrics(){
    document.querySelectorAll('.grid.metrics').forEach(g=>g.classList.add('ktg-metric-grid'));
    document.querySelectorAll('.card').forEach(c=>{if(c.querySelector('.grid.metrics'))c.classList.add('ktg-observation-card')});
  }
  ready(()=>{document.body.classList.add('ktg-quality-ui');improveTouchTargets();improveDenseMetrics();setTimeout(addConfidence,220);window.addEventListener('load',()=>setTimeout(addConfidence,60),{once:true})});
})();
