(()=>{
  const LOCATIONS=[
    ['/', 'Panama City Beach'],
    ['/destin/', 'Destin'],
    ['/okaloosa-island/', 'Okaloosa Island'],
    ['/south-walton/', 'South Walton / 30A'],
    ['/cape-san-blas/', 'Cape San Blas'],
    ['/st-george-island/', 'St. George Island'],
    ['/navarre-beach/', 'Navarre Beach'],
    ['/pensacola-beach/', 'Pensacola Beach'],
    ['/anna-maria-island/', 'Anna Maria Island'],
    ['/siesta-key/', 'Siesta Key'],
    ['/venice/', 'Venice / Nokomis'],
    ['/sanibel/', 'Sanibel / Captiva'],
    ['/fort-myers-beach/', 'Fort Myers Beach'],
    ['/naples/', 'Naples'],
    ['/marco-island/', 'Marco Island']
  ];
  const normalizedPath=()=>{let p=window.location.pathname||'/';if(!p.endsWith('/'))p+='/';return p.replace(/\/+/g,'/');};
  function ensureSearchIntent(){
    if(document.querySelector('script[data-ktg-search-intent]'))return;
    const s=document.createElement('script');s.src='/assets/search-intent.js';s.defer=true;s.dataset.ktgSearchIntent='true';document.head.appendChild(s);
  }
  function renderBeachNav(){
    const shell=document.querySelector('main.shell');if(!shell)return;
    let nav=document.querySelector('.location-switcher');
    if(!nav){nav=document.createElement('nav');nav.className='location-switcher';nav.setAttribute('aria-label','Choose Florida Gulf Coast beach');const hero=shell.querySelector('.hero');if(hero)hero.insertAdjacentElement('afterend',nav);else shell.prepend(nav);}
    const current=normalizedPath();
    nav.innerHTML='';
    const label=document.createElement('label');label.className='location-switcher-label';label.htmlFor='ktg-location-select';label.textContent='Explore beaches';
    const wrap=document.createElement('div');wrap.className='location-select-wrap';
    const select=document.createElement('select');select.id='ktg-location-select';select.className='location-select';select.setAttribute('aria-label','Choose a Florida Gulf Coast beach');
    LOCATIONS.forEach(([href,name])=>{const option=document.createElement('option');option.value=href;option.textContent=name;if(current===href)option.selected=true;select.appendChild(option);});
    select.addEventListener('change',()=>{const target=select.value;if(target&&target!==current)window.location.assign(target);});
    wrap.appendChild(select);nav.appendChild(label);nav.appendChild(wrap);ensureSearchIntent();
  }
  window.KTGBeachNav=renderBeachNav;if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',renderBeachNav,{once:true});else renderBeachNav();
})();
