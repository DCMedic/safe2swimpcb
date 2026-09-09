(()=>{
  const ready=fn=>document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fn,{once:true}):fn();
  const pathLabel=()=>{
    const h1=document.querySelector('h1');
    if(h1)return h1.textContent.replace(/\s+/g,' ').trim().replace(/[.]$/,'');
    return document.title.split('|')[0].trim();
  };
  function ensureBeachNav(){
    if(window.KTGBeachNav){window.KTGBeachNav();return;}
    if(document.querySelector('script[data-ktg-beach-nav]'))return;
    const s=document.createElement('script');
    s.src='/assets/beach-nav.js';s.defer=true;s.dataset.ktgBeachNav='true';
    s.onload=()=>window.KTGBeachNav?.();document.head.appendChild(s);
  }
  function standardizeBrand(){
    const mark=document.querySelector('.brandmark');
    if(!mark)return;
    if(mark.tagName!=='A'){
      const a=document.createElement('a');a.className=mark.className;a.href='/';a.setAttribute('aria-label','Know the Gulf home');
      [...mark.childNodes].forEach(n=>a.appendChild(n));mark.replaceWith(a);
    }else if(!mark.getAttribute('aria-label'))mark.setAttribute('aria-label','Know the Gulf home');
  }
  function ensureBreadcrumb(){
    const main=document.querySelector('main.shell');
    const hero=main?.querySelector('.hero');
    if(!main||!hero||location.pathname==='/')return;
    let crumb=main.querySelector('.seo-breadcrumb');
    if(!crumb){
      crumb=document.createElement('nav');crumb.className='seo-breadcrumb ktg-standard-breadcrumb';crumb.setAttribute('aria-label','Breadcrumb');
      crumb.innerHTML=`<a href="/">Know the Gulf</a><span aria-hidden="true">›</span><span>${pathLabel()}</span>`;
      hero.insertAdjacentElement('afterend',crumb);
    }else crumb.setAttribute('aria-label','Breadcrumb');
  }
  function standardizeSafety(){
    document.querySelectorAll('.safety').forEach(x=>x.setAttribute('role','note'));
  }
  function standardizeFooter(){
    const main=document.querySelector('main.shell');if(!main)return;
    let f=main.querySelector('footer.footer');
    if(!f){f=document.createElement('footer');f.className='footer';main.appendChild(f);}
    f.innerHTML=`<div class="ktg-footer-grid"><div><strong>Know the Gulf</strong><div class="small">Florida Gulf Coast beach safety, conditions and provenance-aware planning data.</div></div><nav class="ktg-footer-links" aria-label="Footer"><a href="/">Home</a><a href="/guides/">Guides</a><a href="/florida-beach-flag-meanings/">Flag meanings</a><a href="/rip-current-safety/">Rip-current safety</a><a href="mailto:contact@knowthegulf.com">Contact</a></nav></div><div class="small ktg-footer-note">Informational planning only. Posted flags, lifeguards and local authorities always control.</div>`;
  }
  function accessibility(){
    const main=document.querySelector('main.shell');if(!main)return;
    main.id=main.id||'main-content';
    if(!document.querySelector('.ktg-skip-link')){
      const a=document.createElement('a');a.href='#main-content';a.className='ktg-skip-link';a.textContent='Skip to main content';document.body.prepend(a);
    }
  }
  const FLAG_PATHS={
    '/':'/data/current_flag.json',
    '/destin/':'/data/destin/current_flag.json',
    '/okaloosa-island/':'/data/okaloosa-island/current_flag.json',
    '/navarre-beach/':'/data/navarre-beach/current_flag.json',
    '/pensacola-beach/':'/data/pensacola-beach/current_flag.json',
    '/south-walton/':'/data/south-walton/current_flag.json',
    '/cape-san-blas/':'/data/cape-san-blas/current_flag.json',
    '/st-george-island/':'/data/franklin-county/current_flag.json',
    '/anna-maria-island/':'/data/anna-maria-island/current_flag.json',
    '/siesta-key/':'/data/siesta-key/current_flag.json',
    '/venice/':'/data/venice/current_flag.json',
    '/sanibel/':'/data/sanibel/current_flag.json',
    '/fort-myers-beach/':'/data/fort-myers-beach/current_flag.json',
    '/naples/':'/data/naples/current_flag.json',
    '/marco-island/':'/data/marco-island/current_flag.json'
  };
  const VISITBEACHES_SLUGS={
    '/':'pcb','/destin/':'destin','/okaloosa-island/':'okaloosa-island','/navarre-beach/':'navarre-beach','/pensacola-beach/':'pensacola-beach',
    '/south-walton/':'south-walton','/cape-san-blas/':'cape-san-blas','/st-george-island/':'franklin-county','/anna-maria-island/':'anna-maria-island',
    '/siesta-key/':'siesta-key','/venice/':'venice','/sanibel/':'sanibel','/fort-myers-beach/':'fort-myers-beach','/naples/':'naples','/marco-island/':'marco-island'
  };
  function normalizedPath(){let p=location.pathname||'/';if(!p.endsWith('/'))p+='/';return p.replace(/\/+/g,'/');}
  function flagColor(primary){
    if(primary==='Green')return'var(--good)';
    if(primary==='Red'||primary==='Single Red'||primary==='Double Red')return'var(--red)';
    return'var(--yellow)';
  }
  function canonicalFlagLabel(c){
    const primary=c.primary_flag||c.flag||null,purple=c.purple===true;
    if(primary&&purple)return`${primary} + Purple`;
    if(primary)return primary;
    if(purple)return'Purple';
    return null;
  }
  function flagFreshness(c){
    const verified=c.last_verified_at?new Date(c.last_verified_at):null;
    const validTime=verified&&!Number.isNaN(verified.getTime());
    const age=validTime?(Date.now()-verified.getTime())/36e5:Infinity;
    const limit=Number(c.stale_after_hours||0);
    const hasFlag=Boolean(c.primary_flag||c.flag||c.purple===true);
    return{verified:validTime?verified:null,stale:hasFlag&&(!validTime||limit<=0||age>limit)};
  }
  function renderCanonicalPole(pole,c,stale=false){
    if(!pole)return;
    const primary=c.primary_flag||c.flag||null,purple=c.purple===true;
    if(!primary&&!purple){pole.hidden=true;pole.innerHTML='';return;}
    const shapes=[];
    if(primary==='Double Red'){
      shapes.push(flagColor(primary),flagColor(primary));
    }else if(primary){
      shapes.push(flagColor(primary));
    }
    if(purple)shapes.push('var(--purple)');
    pole.className='flagpole';pole.hidden=false;
    pole.style.height=shapes.length>=3?'106px':shapes.length===2?'82px':'70px';
    pole.innerHTML=shapes.map((color,i)=>`<span class="flagshape" style="top:${5+i*31}px;background:${color}"></span>`).join('');
    const label=canonicalFlagLabel(c);
    pole.setAttribute('role','img');
    pole.setAttribute('aria-label',`${stale?'Last verified':'Current'} beach flag${primary&&purple?'s':''}: ${label}`);
  }
  async function syncCanonicalFlagVisual(){
    const url=FLAG_PATHS[normalizedPath()];if(!url)return;
    try{
      let c=url==='/data/current_flag.json'?window.__KTG_CURRENT_FLAG_DATA:null;
      if(!c){
        const r=await fetch(url,{cache:'no-store'});if(!r.ok)return;
        c=await r.json();
        if(url==='/data/current_flag.json')window.__KTG_CURRENT_FLAG_DATA=c;
      }
      const flagLabel=canonicalFlagLabel(c);
      const {stale}=flagFreshness(c);
      const displayLabel=flagLabel?(stale?`Last verified flag: ${flagLabel}`:flagLabel):(c.label||null);
      if(displayLabel){
        const name=document.getElementById('currentFlag')||document.getElementById('currentStatus');
        if(name)name.textContent=displayLabel;
      }
      renderCanonicalPole(document.getElementById('flagPole'),c,stale);
    }catch(_){/* Existing page-specific fallback remains authoritative on fetch failure. */}
  }
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const clean=s=>String(s??'').replace(/\s+/g,' ').trim();
  function paramValue(obs,name){
    const target=name.toLowerCase();
    const p=(obs.parameters||[]).find(x=>clean(x.parameter).toLowerCase()===target);
    if(!p)return null;
    if(p.value!==null&&p.value!==undefined&&String(p.value)!=='')return{value:p.value,unit:p.unit||''};
    const vals=(p.selected_values||[]).map(v=>v.name).filter(Boolean);
    return vals.length?{value:vals.join(', '),unit:p.unit||''}:null;
  }
  function firstParam(obs,names){for(const name of names){const v=paramValue(obs,name);if(v)return v}return null;}
  function fmtValue(v){if(!v)return null;const value=clean(v.value);if(!value)return null;return `${value}${v.unit?` ${clean(v.unit)}`:''}`.trim();}
  function observationMetrics(obs){
    const n=obs.normalized_conditions||{};
    const temp=n.water_temperature?fmtValue(n.water_temperature):fmtValue(firstParam(obs,['Water Surface Temperature','Water Temperature']));
    const air=fmtValue(firstParam(obs,['Air Temperature']));
    const uv=fmtValue(firstParam(obs,['UV Index']));
    const surfHeight=fmtValue(firstParam(obs,['Surf Height','Wave Height']));
    const surfType=fmtValue(firstParam(obs,['Surf Type']));
    const rip=fmtValue(firstParam(obs,['Rip Currents','Rip Current']));
    const windSpeed=fmtValue(firstParam(obs,['Wind Speed'])),windDir=fmtValue(firstParam(obs,['Wind Direction']));
    const wind=[windDir,windSpeed].filter(Boolean).join(' · ')||null;
    const tide=fmtValue(firstParam(obs,['Tides','Tide']));
    const waterColor=n.water_color?clean(n.water_color):fmtValue(firstParam(obs,['Water Color']));
    const respiratory=n.respiratory_irritation?clean(n.respiratory_irritation):fmtValue(firstParam(obs,['Respiratory Irritation']));
    const deadFish=n.dead_fish?clean(n.dead_fish):fmtValue(firstParam(obs,['Dead Fish']));
    const crowds=n.crowd?clean(n.crowd):fmtValue(firstParam(obs,['Crowds','Crowd']));
    const jelly=fmtValue(firstParam(obs,['Jellyfish']));
    const algae=fmtValue(firstParam(obs,['Drift Algae','Algae']));
    const debris=fmtValue(firstParam(obs,['Beach Debris','Debris']));
    return[
      ['Water temperature',temp,'Observed'],['Surf height',surfHeight,surfType||'Observed surf'],['Rip currents',rip,'Ambassador observation'],['Wind',wind,'Observed'],
      ['Tides',tide,'Reported tide times'],['Water color',waterColor,'Observed'],['Jellyfish',jelly,'Observed'],['Respiratory irritation',respiratory,'Observed'],
      ['Dead fish',deadFish,'Observed'],['Crowds',crowds,'Observed'],['Drift algae',algae,'Observed'],['Beach debris',debris,'Observed'],['Air temperature',air,'Observed'],['UV index',uv,'Reported']
    ].filter(x=>x[1]);
  }
  function metricHtml(label,value,sub){return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`;}
  async function renderVisitBeachesObservation(){
    const slug=VISITBEACHES_SLUGS[normalizedPath()];if(!slug)return;
    try{
      const r=await fetch(`/data/visitbeaches/${slug}.json`,{cache:'no-store'});if(!r.ok)return;
      const d=await r.json(),observations=Array.isArray(d.observations)?d.observations:[];
      const obs=observations.find(x=>x&&x.fresh&&observationMetrics(x).length)||observations.find(x=>x&&observationMetrics(x).length);
      if(!obs)return;
      const metrics=observationMetrics(obs);if(!metrics.length)return;
      const main=document.querySelector('main.shell');if(!main||document.getElementById('ktgAmbassadorObservation'))return;
      const anchor=main.querySelector('.flag-card')||main.querySelector('.flag-card-wide')||main.querySelector('.today-grid')||main.querySelector('.hero');if(!anchor)return;
      const stamp=obs.created_at?new Date(obs.created_at):null,validStamp=stamp&&!Number.isNaN(stamp.getTime());
      const fresh=obs.fresh===true;
      const section=document.createElement('section');section.id='ktgAmbassadorObservation';section.className='card';section.setAttribute('aria-labelledby','ktgAmbassadorTitle');
      const status=fresh?'Fresh Beach Ambassador observation':'Last Beach Ambassador observation';
      const confidence=d.knowthegulf_comparison?.state||null;
      section.innerHTML=`<div class="eyebrow">Mote Marine Laboratory · VisitBeaches</div><h2 id="ktgAmbassadorTitle">Beach Ambassador Observation</h2><p>${esc(status)}${obs.beach_name?` for <strong>${esc(obs.beach_name)}</strong>`:''}${validStamp?` · ${esc(stamp.toLocaleString())}`:''}. These are observational conditions and do not replace posted flags or lifeguard instructions.</p><div class="pillrow"><span class="pill">Beach Ambassador report</span>${confidence?`<span class="pill">Source comparison: ${esc(confidence.replaceAll('_',' '))}</span>`:''}</div><div class="grid metrics" style="margin-top:14px">${metrics.map(x=>metricHtml(...x)).join('')}</div><p class="small" style="margin-top:14px"><a href="https://visitbeaches.org/map" target="_blank" rel="noopener">Open VisitBeaches source ↗</a></p>`;
      anchor.insertAdjacentElement('afterend',section);
    }catch(_){/* Rich observational data is optional; core safety status remains available. */}
  }
  ready(()=>{
    document.body.classList.add('ktg-standard-ui');
    accessibility();standardizeBrand();ensureBreadcrumb();ensureBeachNav();standardizeSafety();standardizeFooter();
    setTimeout(syncCanonicalFlagVisual,250);
    setTimeout(renderVisitBeachesObservation,300);
    window.addEventListener('load',()=>{setTimeout(syncCanonicalFlagVisual,50);setTimeout(renderVisitBeachesObservation,80)},{once:true});
  });
})();
