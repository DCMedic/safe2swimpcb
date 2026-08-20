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
  function normalizedPath(){let p=location.pathname||'/';if(!p.endsWith('/'))p+='/';return p.replace(/\/+/g,'/');}
  function flagColor(primary){
    if(primary==='Green')return'var(--good)';
    if(primary==='Red'||primary==='Single Red'||primary==='Double Red')return'var(--red)';
    return'var(--yellow)';
  }
  function renderCanonicalPole(pole,c){
    if(!pole)return;
    const primary=c.primary_flag||c.flag||null,purple=c.purple===true;
    if(!primary&&!purple)return;
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
    const label=primary&&purple?`${primary} + Purple`:primary||'Purple';
    pole.setAttribute('role','img');pole.setAttribute('aria-label',`Current beach flag${primary&&purple?'s':''}: ${label}`);
  }
  async function syncCanonicalFlagVisual(){
    const url=FLAG_PATHS[normalizedPath()];if(!url)return;
    try{
      const r=await fetch(url,{cache:'no-store'});if(!r.ok)return;
      const c=await r.json();const label=c.label||(c.primary_flag||c.flag)||(c.purple?'Purple':null);
      if(!label)return;
      const name=document.getElementById('currentFlag')||document.getElementById('currentStatus');if(name)name.textContent=label;
      renderCanonicalPole(document.getElementById('flagPole'),c);
    }catch(_){/* Existing page-specific fallback remains authoritative on fetch failure. */}
  }
  ready(()=>{
    document.body.classList.add('ktg-standard-ui');
    accessibility();standardizeBrand();ensureBreadcrumb();ensureBeachNav();standardizeSafety();standardizeFooter();
    setTimeout(syncCanonicalFlagVisual,250);
    window.addEventListener('load',()=>setTimeout(syncCanonicalFlagVisual,50),{once:true});
  });
})();
