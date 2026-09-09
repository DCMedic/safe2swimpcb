(()=>{if(window.KTGBeachNav)window.KTGBeachNav();else if(!document.querySelector('script[data-ktg-beach-nav]')){const s=document.createElement('script');s.src='/assets/beach-nav.js';s.defer=true;s.dataset.ktgBeachNav='';document.head.appendChild(s)}})();

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-southwest-location]');
  if (!root) return;
  const slug = root.dataset.slug;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const getJSON = async u => { const r = await fetch(u, {cache:'no-store'}); if (!r.ok) throw Error(r.status); return r.json(); };
  const flagClass = f => f === 'Green' ? 'green' : (f === 'Red' || f === 'Single Red') ? 'red' : f === 'Double Red' ? 'double' : '';
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

  try {
    const c = await getJSON(`/data/${slug}/current_status.json`);
    applyBase(c);
    $('methodNote').textContent = c.update_note || '';
    $('safetyNote').textContent = c.safety_note || '';

    const st = $('statusFreshness');
    const t = c.last_verified_at ? new Date(c.last_verified_at) : null;
    const validTime = t && !Number.isNaN(t.getTime());
    const age = validTime ? (Date.now() - t.getTime()) / 36e5 : Infinity;
    const limit = Number(c.stale_after_hours || 18);
    const stale = !validTime || limit <= 0 || age > limit;
    const rawLabel = c.label || c.flag || 'Official current conditions unavailable';
    $('currentStatus').textContent = c.flag && stale ? `Last verified flag: ${rawLabel}` : rawLabel;

    st.className = 'status' + (stale || !c.source_reachable ? ' stale' : '');
    if (!c.source_reachable && c.flag) {
      st.innerHTML = `Last verified <strong>${validTime ? esc(t.toLocaleString()) : 'time unavailable'}</strong>. The upstream source could not be reached during the latest check, so this is the last verified flag, not a current-status claim.`;
    } else if (!c.source_reachable) {
      st.textContent = 'The public upstream conditions source could not be reached during the latest check. Use the official authority link and posted beach flags.';
    } else if (stale && c.flag) {
      st.innerHTML = `Last verified <strong>${validTime ? esc(t.toLocaleString()) : 'time unavailable'}</strong>. This is the last verified flag; verify the latest condition at the official source or with lifeguards before entering the water.`;
    } else if (stale) {
      st.textContent = 'The cached source check is stale. Verify conditions at the official source or with lifeguards before entering the water.';
    } else if (c.flag) {
      st.innerHTML = `Explicit upstream flag verified: <strong>${esc(c.flag)}</strong> · checked ${esc(t.toLocaleString())}`;
    } else {
      st.innerHTML = `Official current-conditions source reachable · checked <strong>${esc(t.toLocaleString())}</strong>. No explicit machine-verifiable flag was found, so Know the Gulf does not display one.`;
    }

    const pole = $('flagPole');
    if (c.flag) {
      pole.className = 'flagpole ' + flagClass(c.flag);
      pole.hidden = false;
      if (pole.children[1]) pole.children[1].hidden = c.flag !== 'Double Red';
      pole.setAttribute('role','img');
      pole.setAttribute('aria-label', `${stale ? 'Last verified' : 'Current'} beach flag: ${rawLabel}`);
    } else {
      pole.hidden = true;
    }
  } catch (e) {
    $('currentStatus').textContent = 'Open official current conditions';
    $('methodNote').textContent = 'The automated cache has not populated yet or is temporarily unavailable. The direct official/current-conditions links remain available above.';
    $('safetyNote').textContent = 'Know the Gulf does not infer a flag from weather, surf, red tide, water quality, or generic hazard scores. Posted flags and lifeguard instructions control.';
    $('statusFreshness').className = 'status stale';
    $('statusFreshness').textContent = 'Automated Southwest status cache unavailable; use the live official source.';
    const pole = $('flagPole'); if (pole) pole.hidden = true;
  }
});
