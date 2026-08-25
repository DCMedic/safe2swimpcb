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
  function ensureStyles(){
    if(document.getElementById('ktg-beach-nav-styles'))return;
    const style=document.createElement('style');style.id='ktg-beach-nav-styles';style.textContent=`
      .location-switcher{align-items:center}.location-select-wrap{flex:1;min-width:0}.location-select{width:100%;min-height:44px;padding:10px 42px 10px 14px;border:1px solid #b9dfe3;border-radius:12px;background:#fff;color:var(--navy);font:inherit;font-size:16px;font-weight:800;cursor:pointer}.location-select:hover,.location-select:focus-visible{border-color:var(--accent);outline:2px solid transparent;box-shadow:0 0 0 3px rgba(17,174,184,.16)}.search-intent-section{margin-top:28px}.search-intent-grid{margin-top:14px}.search-intent-item{min-width:0;padding:14px;border:1px solid var(--line);border-radius:14px;background:#f8fcfc}.search-intent-item h3{font-size:1rem;margin:0 0 8px}.search-intent-item p{margin:0;font-size:.9rem}@media(max-width:700px){.location-switcher{align-items:stretch}.location-select-wrap{width:100%}.location-select{width:100%}.search-intent-grid{grid-template-columns:1fr}}
    `;document.head.appendChild(style);
  }
  function ensureSearchIntent(){
    if(document.querySelector('script[data-ktg-search-intent]'))return;
    const s=document.createElement('script');s.src='/assets/search-intent.js';s.defer=true;s.dataset.ktgSearchIntent='true';document.head.appendChild(s);
  }
  function renderBeachNav(){
    const shell=document.querySelector('main.shell');if(!shell)return;
    ensureStyles();
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
