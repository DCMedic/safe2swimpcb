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

  const normalizedPath=()=>{
    let p=window.location.pathname||'/';
    if(!p.endsWith('/'))p+='/';
    return p.replace(/\/+/g,'/');
  };

  function renderBeachNav(){
    const shell=document.querySelector('main.shell');
    if(!shell)return;
    let nav=document.querySelector('.location-switcher');
    if(!nav){
      nav=document.createElement('nav');
      nav.className='location-switcher';
      nav.setAttribute('aria-label','Choose Florida Gulf Coast beach');
      const hero=shell.querySelector('.hero');
      if(hero)hero.insertAdjacentElement('afterend',nav);else shell.prepend(nav);
    }
    const current=normalizedPath();
    nav.innerHTML='<div class="location-switcher-label">Explore beaches</div><div class="location-links"></div>';
    const links=nav.querySelector('.location-links');
    LOCATIONS.forEach(([href,label])=>{
      const a=document.createElement('a');
      a.className='location-link';
      a.href=href;
      a.innerHTML='<span class="location-dot"></span>'+label;
      const target=href==='/'?'/':href;
      if(current===target){a.classList.add('active');a.setAttribute('aria-current','page');}
      links.appendChild(a);
    });
  }

  window.KTGBeachNav=renderBeachNav;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',renderBeachNav,{once:true});
  else renderBeachNav();
})();
