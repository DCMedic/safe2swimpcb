(()=>{if(window.KTGBeachNav)window.KTGBeachNav();else if(!document.querySelector('script[data-ktg-beach-nav]')){const s=document.createElement('script');s.src='/assets/beach-nav.js';s.defer=true;s.dataset.ktgBeachNav='';document.head.appendChild(s)}})();

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-southwest-location]');
  if (!root) return;
  const slug = root.dataset.slug;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const fallback = {
    'anna-maria-island': {authority:'Manatee County Beach Patrol', source:'Safe Beach Day / Manatee County', sourceUrl:'https://safebeachday.com/county/manatee-county/', officialUrl:'https://www.mymanatee.org/services-and-amenities/service-listing/service-details/check-beach-conditions', beaches:['Manatee Public Beach','Coquina Beach','Cortez Beach']},
    'siesta-key': {authority:'Sarasota County Fire Department Lifeguard Operations', source:'Mote Beach Conditions Reporting System / VisitBeaches', sourceUrl:'https://visitbeaches.org/', officialUrl:'https://www.scgov.net/government/emergency-services/lifeguard-operations', beaches:['Siesta Beach']},
    'venice': {authority:'Sarasota County Fire Department Lifeguard Operations', source:'Mote Beach Conditions Reporting System / VisitBeaches', sourceUrl:'https://visitbeaches.org/', officialUrl:'https://www.scgov.net/government/emergency-services/lifeguard-operations', beaches:['Venice Beach','Nokomis Beach','North Jetty','Manasota Beach']},
    'sanibel': {authority:'Lee County Natural Resources / Mote Marine Laboratory', source:'Mote Beach Conditions Reporting System / VisitBeaches', sourceUrl:'https://visitbeaches.org/', officialUrl:'https://www.leefl.gov/naturalresources/WaterQuality/WaterQualityStatus', beaches:['Sanibel','Captiva']},
    'fort-myers-beach': {authority:'Lee County Natural Resources / Mote Marine Laboratory', source:'Mote Beach Conditions Reporting System / VisitBeaches', sourceUrl:'https://visitbeaches.org/', officialUrl:'https://www.leefl.gov/naturalresources/WaterQuality/WaterQualityStatus', beaches:['Fort Myers Beach']},
    'naples': {authority:'Collier County Pollution Control / Mote Marine Laboratory', source:'Mote Beach Conditions Reporting System / VisitBeaches', sourceUrl:'https://visitbeaches.org/', officialUrl:'https://www.collier.gov/County-Development/Transportation-Management/Pollution-Control/Red-Tide/Red-Tide-Status', beaches:['Vanderbilt Beach','Seagate Beach','Naples Pier','Barefoot Beach']},
    'marco-island': {authority:'Collier County Pollution Control / Mote Marine Laboratory', source:'Mote Beach Conditions Reporting System / VisitBeaches', sourceUrl:'https://visitbeaches.org/', officialUrl:'https://www.collier.gov/County-Development/Transportation-Management/Pollution-Control/Red-Tide/Red-Tide-Status', beaches:['South Marco Beach']}
  }[slug];

  function applyBase(c) {
    $('authority').textContent = c.official_authority || c.authority || 'Local beach-safety authority';
    $('sourceSystem').textContent = c.source_name || c.source || 'Official current-conditions source';
    $('sourceLink').href = c.source_url || c.sourceUrl || '#';
    $('officialLink').href = c.official_authority_url || c.officialUrl || '#';
    $('beachList').innerHTML = (c.beaches || []).map(x => `<li>${esc(x)}</li>`).join('');
  }
  if (fallback) applyBase(fallback);

  // Live status is rendered atomically by safety-ui.js from current_flag.json.
});
