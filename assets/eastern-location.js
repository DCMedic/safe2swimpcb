document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-east-location]');
  if (!root) return;
  const primary = root.dataset.primary;
  const related = (root.dataset.related || '').split(',').filter(Boolean);
  const $ = id => document.getElementById(id);
  const j = async u => { const r = await fetch(u, {cache:'no-store'}); if (!r.ok) throw Error(r.status); return r.json(); };
  const cls = f => f === 'Green' ? 'green' : f === 'Red' ? 'red' : f === 'Double Red' ? 'double' : '';
  const esc = s => String(s ?? '').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function renderFlag(c){
    $('currentFlag').textContent = c.label || 'Official flag status unavailable';
    const pole = $('flagPole'); pole.className = 'flagpole ' + cls(c.flag); pole.children[1].hidden = c.flag !== 'Double Red';
    const verified = c.last_verified_at ? new Date(c.last_verified_at) : null;
    const age = verified ? (Date.now()-verified.getTime())/36e5 : Infinity;
    const stale = !c.flag || age > Number(c.stale_after_hours || 0);
    $('flagFreshness').className = 'status flag-status' + (stale ? ' stale' : '');
    $('flagFreshness').innerHTML = stale
      ? 'Official flag status is unavailable or stale. Use the linked local authority before entering the Gulf.'
      : `Verified <strong>${verified.toLocaleString()}</strong> · provenance: <strong>${esc(c.provenance_tier)}</strong>`;
    $('sourceDisclosure').innerHTML = `<strong>Source:</strong> <a href="${esc(c.source_url)}" target="_blank" rel="noopener">${esc(c.source_name)} ↗</a><br><strong>Authority:</strong> <a href="${esc(c.official_authority_url)}" target="_blank" rel="noopener">${esc(c.official_authority)} ↗</a><br><strong>Method:</strong> ${esc(c.method)}${c.corroborates_primary ? '<br><strong>Cross-check:</strong> NWS reported the same flag.' : ''}`;
  }
  function relatedCard(c){ return `<div class="card"><div class="eyebrow">${esc(c.location)}</div><h3>${esc(c.label || 'Unavailable')}</h3><p>${esc(c.source_note || '')}</p><a href="${esc(c.official_authority_url)}" target="_blank" rel="noopener">Official safety source ↗</a></div>`; }
  try { renderFlag(await j(`/data/${primary}/current_flag.json`)); }
  catch { $('currentFlag').textContent='Official flag status unavailable'; $('flagFreshness').className='status stale'; $('flagFreshness').textContent='Current status cache unavailable. Use the official source below.'; }
  if (related.length) {
    const rows = await Promise.all(related.map(async s => { try { return await j(`/data/${s}/current_flag.json`); } catch { return null; } }));
    $('relatedFlags').innerHTML = rows.filter(Boolean).map(relatedCard).join('');
  }
});
