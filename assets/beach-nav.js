(()=>{
  const LOCATIONS=[
    ['/', 'Panama City Beach', ''],
    ['/destin/', 'Destin', 'destin'],
    ['/okaloosa-island/', 'Okaloosa Island', 'okaloosa-island'],
    ['/south-walton/', 'South Walton / 30A', 'south-walton'],
    ['/cape-san-blas/', 'Cape San Blas', 'cape-san-blas'],
    ['/st-george-island/', 'St. George Island', 'franklin-county'],
    ['/navarre-beach/', 'Navarre Beach', 'navarre-beach'],
    ['/pensacola-beach/', 'Pensacola Beach', 'pensacola-beach'],
    ['/anna-maria-island/', 'Anna Maria Island', 'anna-maria-island'],
    ['/siesta-key/', 'Siesta Key', 'siesta-key'],
    ['/venice/', 'Venice / Nokomis', 'venice'],
    ['/sanibel/', 'Sanibel / Captiva', 'sanibel'],
    ['/fort-myers-beach/', 'Fort Myers Beach', 'fort-myers-beach'],
    ['/naples/', 'Naples', 'naples'],
    ['/marco-island/', 'Marco Island', 'marco-island']
  ];
  const FLAG_COLORS={'Green':'var(--good)','Yellow':'var(--yellow)','Red':'var(--red)','Single Red':'var(--red)','Double Red':'var(--red)','Purple':'var(--purple)'};
  const normalizedPath=()=>{let p=window.location.pathname||'/';if(!p.endsWith('/'))p+='/';return p.replace(/\/+/g,'/');};
  const flagUrl=slug=>slug?`/data/${slug}/current_flag.json`:'/data/current_flag.json';
  async function colorDot(dot,slug){
    try{
      const r=await fetch(flagUrl(slug),{cache:'no-store'});if(!r.ok)return;
      const c=await r.json();
      const primary=c.primary_flag||c.flag||null,purple=c.purple===true;
      const primaryColor=FLAG_COLORS[primary],purpleColor=FLAG_COLORS.Purple;
      if(!primaryColor&&!purple)return;
      if(primaryColor&&purple){
        dot.style.background=`linear-gradient(135deg, ${primaryColor} 0 50%, ${purpleColor} 50% 100%)`;
        dot.style.boxShadow=`0 0 0 3px color-mix(in srgb, ${primaryColor} 18%, ${purpleColor} 10%)`;
      }else{
        const color=primaryColor||purpleColor;
        dot.style.background=color;dot.style.boxShadow=`0 0 0 3px color-mix(in srgb, ${color} 22%, transparent)`;
      }
      const label=primary&&purple?`${primary} + Purple`:primary||'Purple';
      dot.dataset.flag=label;dot.title=`Current flag${primary&&purple?'s':''}: ${label}`;
    }catch(_){/* Keep neutral dot when a verified flag is unavailable. */}
  }
  function renderBeachNav(){
    const shell=document.querySelector('main.shell');if(!shell)return;
    let nav=document.querySelector('.location-switcher');
    if(!nav){nav=document.createElement('nav');nav.className='location-switcher';nav.setAttribute('aria-label','Choose Florida Gulf Coast beach');const hero=shell.querySelector('.hero');if(hero)hero.insertAdjacentElement('afterend',nav);else shell.prepend(nav);}
    const current=normalizedPath();nav.innerHTML='<div class="location-switcher-label">Explore beaches</div><div class="location-links"></div>';const links=nav.querySelector('.location-links');
    LOCATIONS.forEach(([href,label,slug])=>{const a=document.createElement('a');a.className='location-link';a.href=href;const dot=document.createElement('span');dot.className='location-dot';dot.setAttribute('aria-hidden','true');a.appendChild(dot);a.appendChild(document.createTextNode(label));const target=href==='/'?'/':href;if(current===target){a.classList.add('active');a.setAttribute('aria-current','page');}links.appendChild(a);colorDot(dot,slug);});
  }
  window.KTGBeachNav=renderBeachNav;if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',renderBeachNav,{once:true});else renderBeachNav();
})();
