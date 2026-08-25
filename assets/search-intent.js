(()=>{
  const PAGES={
    '/':{
      heading:'Panama City Beach conditions today',
      intro:'Looking for the current Panama City Beach flag, rip-current context, surf, water conditions, waves, wind or tide? Know the Gulf keeps today’s PCB beach-safety signal beside the environmental context visitors commonly check before heading to the sand.',
      items:[
        ['Panama City Beach flag today','The posted PCB beach flag is the controlling public-safety signal. Know the Gulf displays the latest locally cached official status and links directly to the official Panama City Beach source.'],
        ['PCB rip currents and surf','Wave, wind and surf context can help explain conditions, but they never replace posted flags, lifeguards or local authority guidance.'],
        ['Panama City Beach water conditions','Current marine context is presented alongside historical observations so visitors can understand today’s conditions without treating a forecast or model as swimming clearance.']
      ]
    },
    '/destin/':{
      heading:'Destin beach conditions today',
      intro:'Searchers looking for the Destin beach flag color today, Destin rip-current forecast, surf report, water temperature or Gulf conditions can find those signals together here, with official beach-safety guidance kept separate from modeled environmental data.',
      items:[
        ['Destin beach flag today','Know the Gulf links to Destin Beach Safety for the controlling warning condition and preserves the distinction between an official posted flag and forecast hazard data.'],
        ['Destin rip-current forecast','NWS Mobile/Pensacola coastal forecasts provide rip-current risk and surf context for the Okaloosa Coastal zone, including Destin.'],
        ['Destin water and surf conditions','Wind, waves, tide and modeled Gulf temperature provide additional trip-planning context for visitors checking conditions before going to the beach.']
      ]
    },
    '/okaloosa-island/':{
      heading:'Okaloosa Island beach flag and conditions today',
      intro:'Use this page to check Okaloosa Island beach-safety resources, rip-current risk, surf, wind, waves, tide and Gulf temperature without confusing forecast conditions with the official county flag.',
      items:[
        ['Okaloosa Island flag today','Okaloosa County Beach Safety remains the authoritative source for the posted flag. Know the Gulf links visitors directly to county guidance rather than inferring a flag from weather data.'],
        ['Okaloosa Island rip currents','NWS forecasts for the Okaloosa Coastal zone provide daily rip-current and surf context for Okaloosa Island and nearby beaches.'],
        ['Okaloosa Island water conditions','Live environmental measurements and models add useful context for beach planning while posted flags and lifeguard instructions remain controlling.']
      ]
    },
    '/cape-san-blas/':{
      heading:'Cape San Blas beach flag today',
      intro:'Check the current Cape San Blas and Indian Pass flag status, Gulf County beach-safety guidance and related local flag zones. Know the Gulf preserves jurisdiction-specific reporting so visitors do not mistake one Gulf County beach status for another.',
      items:[
        ['Cape San Blas flag color today','The Cape San Blas / Indian Pass status is shown from authoritative local evidence and linked back to Gulf County beach-safety guidance.'],
        ['Gulf County flags today','Gulf County contains multiple flag-management zones. Know the Gulf keeps Cape San Blas, state-park beaches and St. Joe Beach evidence separate rather than assigning one countywide flag.'],
        ['Cape San Blas beach safety','Posted flags and local officials always control. Rip-current forecasts and weather may provide context but are never converted into an official flag.']
      ]
    },
    '/naples/':{
      heading:'Naples beach conditions today',
      intro:'Check current Naples and Collier County beach-condition sources, including beach advisories and environmental reporting, with red-tide information clearly separated from swimming-flag evidence.',
      items:[
        ['Naples beach conditions today','Know the Gulf points visitors to current official-source reporting for Naples-area beaches and identifies the authority behind the displayed status.'],
        ['Naples water quality and red tide','Environmental and red-tide reporting can affect a beach visit, but those signals are presented separately from swimming flags and other public-safety controls.'],
        ['Collier County beach safety','Local authorities and posted guidance remain controlling. Know the Gulf emphasizes source provenance so visitors can verify the latest official information.']
      ]
    }
  };
  const path=(()=>{let p=location.pathname||'/';if(!p.endsWith('/'))p+='/';return p.replace(/\/+/g,'/');})();
  const data=PAGES[path];if(!data)return;
  const run=()=>{
    const main=document.querySelector('main.shell');if(!main||main.querySelector('.search-intent-section'))return;
    const safety=main.querySelector('.safety-bottom');
    const section=document.createElement('section');section.className='card search-intent-section';section.setAttribute('aria-labelledby','search-intent-heading');
    const h=document.createElement('h2');h.id='search-intent-heading';h.textContent=data.heading;section.appendChild(h);
    const p=document.createElement('p');p.textContent=data.intro;section.appendChild(p);
    const grid=document.createElement('div');grid.className='grid three search-intent-grid';
    data.items.forEach(([title,text])=>{const article=document.createElement('article');article.className='search-intent-item';const h3=document.createElement('h3');h3.textContent=title;const body=document.createElement('p');body.textContent=text;article.append(h3,body);grid.appendChild(article);});
    section.appendChild(grid);
    if(safety)safety.insertAdjacentElement('beforebegin',section);else main.appendChild(section);

    const schema={
      '@context':'https://schema.org','@type':'WebPage',url:location.href.split('#')[0],name:document.title.split('|')[0].trim(),
      about:data.items.map(([name])=>({'@type':'Thing',name})),isPartOf:{'@type':'WebSite',name:'Know the Gulf',url:'https://knowthegulf.com/'}
    };
    const script=document.createElement('script');script.type='application/ld+json';script.dataset.ktgSearchIntent='true';script.textContent=JSON.stringify(schema);document.head.appendChild(script);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
