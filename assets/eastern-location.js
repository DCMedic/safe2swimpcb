(()=>{if(window.KTGBeachNav)window.KTGBeachNav();else if(!document.querySelector('script[data-ktg-beach-nav]')){const s=document.createElement('script');s.src='/assets/beach-nav.js';s.defer=true;s.dataset.ktgBeachNav='';document.head.appendChild(s)}})();

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-east-location]');
  if (!root) return;
  const primary = root.dataset.primary;
  const related = (root.dataset.related || '').split(',').filter(Boolean);
  const $ = id => document.getElementById(id);
  const j = async u => { const r = await fetch(u, {cache:'no-store'}); if (!r.ok) throw Error(r.status); return r.json(); };
  const cls = f => f === 'Green' ? 'green' : (f === 'Red' || f === 'Single Red') ? 'red' : f === 'Double Red' ? 'double' : '';
  const esc = s => String(s ?? '').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[m]));
  const freshness = c => {
    const verified = c.last_verified_at ? new Date(c.last_verified_at) : null;
    const validTime = verified && !Number.isNaN(verified.getTime());
    const age = validTime ? (Date.now()-verified.getTime())/36e5 : Infinity;
    const limit = Number(c.stale_after_hours || 0);
    return {verified:validTime ? verified : null, stale:!c.flag || !validTime || limit <= 0 || age > limit};
  };
  function renderFlag(c){
    const {verified, stale} = freshness(c);
    const rawLabel = c.label || c.flag || 'Official flag status unavailable';
    $('currentFlag').textContent = c.flag && stale ? `Last verified flag: ${rawLabel}` : rawLabel;
    const pole = $('flagPole');
    pole.className = 'flagpole ' + cls(c.flag);
    if (pole.children[1]) pole.children[1].hidden = c.flag !== 'Double Red';
    if (c.flag) {
      pole.hidden = false;
      pole.setAttribute('role','img');
      pole.setAttribute('aria-label', `${stale ? 'Last verified' : 'Current'} beach flag: ${rawLabel}`);
    } else {
      pole.hidden = true;
    }
    $('flagFreshness').className = 'status flag-status' + (stale ? ' stale' : '');
    if (c.flag && stale) {
      $('flagFreshness').innerHTML = `Last verified <strong>${verified ? esc(verified.toLocaleString()) : 'time unavailable'}</strong>. This is the last verified flag, not a claim that the flag is still current. Check the linked local authority for the latest posted condition.`;
    } else if (stale) {
      $('flagFreshness').innerHTML = 'Official flag status is unavailable. Use the linked local authority before entering the Gulf.';
    } else {
      $('flagFreshness').innerHTML = `Verified <strong>${esc(verified.toLocaleString())}</strong> · provenance: <strong>${esc(c.provenance_tier)}</strong>`;
    }
    $('sourceDisclosure').innerHTML = `<strong>Source:</strong> <a href="${esc(c.source_url)}" target="_blank" rel="noopener">${esc(c.source_name)} ↗</a><br><strong>Authority:</strong> <a href="${esc(c.official_authority_url)}" target="_blank" rel="noopener">${esc(c.official_authority)} ↗</a><br><strong>Method:</strong> ${esc(c.method)}${c.corroborates_primary ? '<br><strong>Cross-check:</strong> NWS reported the same flag.' : ''}`;
  }
  function relatedCard(c){
    const {verified, stale} = freshness(c);
    const rawLabel = c.label || c.flag || 'Unavailable';
    const heading = c.flag && stale ? `Last verified flag: ${rawLabel}` : rawLabel;
    const freshnessNote = c.flag && stale
      ? `<p class="small">Last verified ${esc(verified ? verified.toLocaleString() : 'time unavailable')}. Verify the latest condition with the official source.</p>`
      : '';
    return `<div class="card"><div class="eyebrow">${esc(c.location)}</div><h3>${esc(heading)}</h3>${freshnessNote}<p>${esc(c.source_note || '')}</p><a href="${esc(c.official_authority_url)}" target="_blank" rel="noopener">Official safety source ↗</a></div>`;
  }
  try { renderFlag(await j(`/data/${primary}/current_flag.json`)); }
  catch { $('currentFlag').textContent='Official flag status unavailable'; $('flagFreshness').className='status stale'; $('flagFreshness').textContent='Current status cache unavailable. Use the official source below.'; const pole=$('flagPole'); if(pole) pole.hidden=true; }
  if (related.length) {
    const rows = await Promise.all(related.map(async s => { try { return await j(`/data/${s}/current_flag.json`); } catch { return null; } }));
    $('relatedFlags').innerHTML = rows.filter(Boolean).map(relatedCard).join('');
  }
});
