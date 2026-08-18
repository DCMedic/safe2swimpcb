document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-southwest-location]');
  if (!root) return;
  const slug = root.dataset.slug;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const getJSON = async u => { const r = await fetch(u, {cache:'no-store'}); if (!r.ok) throw Error(r.status); return r.json(); };
  const flagClass = f => f === 'Green' ? 'green' : f === 'Red' ? 'red' : f === 'Double Red' ? 'double' : '';
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
    $('currentStatus').textContent = c.label || 'Official current conditions unavailable';
    $('methodNote').textContent = c.update_note || '';
    $('safetyNote').textContent = c.safety_note || '';

    const st = $('statusFreshness');
    const t = c.last_verified_at ? new Date(c.last_verified_at) : null;
    const age = t ? (Date.now() - t.getTime()) / 36e5 : Infinity;
    const stale = age > Number(c.stale_after_hours || 18);
    st.className = 'status' + (stale || !c.source_reachable ? ' stale' : '');
    if (!c.source_reachable) {
      st.textContent = 'The public upstream conditions source could not be reached during the latest check. Use the official authority link and posted beach flags.';
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
    } else {
      pole.hidden = true;
    }
  } catch (e) {
    $('currentStatus').textContent = 'Open official current conditions';
    $('methodNote').textContent = 'The automated cache has not populated yet or is temporarily unavailable. The direct official/current-conditions links remain available above.';
    $('safetyNote').textContent = 'Know the Gulf does not infer a flag from weather, surf, red tide, water quality, or generic hazard scores. Posted flags and lifeguard instructions control.';
    $('statusFreshness').className = 'status stale';
    $('statusFreshness').textContent = 'Automated Southwest status cache unavailable; use the live official source.';
  }
});
