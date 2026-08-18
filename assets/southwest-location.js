document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-southwest-location]');
  if (!root) return;
  const slug = root.dataset.slug;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const getJSON = async u => { const r = await fetch(u, {cache:'no-store'}); if (!r.ok) throw Error(r.status); return r.json(); };
  const flagClass = f => f === 'Green' ? 'green' : f === 'Red' ? 'red' : f === 'Double Red' ? 'double' : '';

  try {
    const c = await getJSON(`/data/${slug}/current_status.json`);
    $('currentStatus').textContent = c.label || 'Official current conditions unavailable';
    $('authority').textContent = c.official_authority || 'Local beach-safety authority';
    $('sourceSystem').textContent = c.source_name || 'Official current-conditions source';
    $('sourceLink').href = c.source_url;
    $('officialLink').href = c.official_authority_url;
    $('beachList').innerHTML = (c.beaches || []).map(x => `<li>${esc(x)}</li>`).join('');
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
    $('currentStatus').textContent = 'Official current conditions unavailable';
    $('statusFreshness').className = 'status stale';
    $('statusFreshness').textContent = 'Know the Gulf could not load the cached Southwest conditions record. Use the official source before entering the water.';
  }
});
