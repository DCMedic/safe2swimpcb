/* The only writer of live safety headings, graphics, freshness and confidence. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./safety-state.js'));
  else { root.KTGSafetyUI = factory(root.KTGSafety); root.KTGSafetyUI.start(); }
})(typeof globalThis !== 'undefined' ? globalThis : this, function(Safety) {
  'use strict';
  const PATHS = {'/':'/data/current_flag.json','/st-george-island/':'/data/franklin-county/current_flag.json'};
  for (const slug of ['destin','okaloosa-island','navarre-beach','pensacola-beach','south-walton','cape-san-blas','anna-maria-island','siesta-key','venice','sanibel','fort-myers-beach','naples','marco-island']) PATHS[`/${slug}/`] = `/data/${slug}/current_flag.json`;
  const safeUrl = value => { try { const u = new URL(value); return ['https:','http:'].includes(u.protocol) ? u.href : null; } catch (_) { return null; } };
  function createController({url,render,fetcher = fetch,clock = Date.now,timeoutMs = 12000}) {
    let generation = 0, snapshot = null, failure = null, aborter = null, disposed = false, lastRender = null;
    const recheck = () => {
      if (disposed) return;
      const state = Safety.derive(snapshot,clock(),failure), signature = JSON.stringify(state);
      if (signature !== lastRender) { lastRender = signature; render(state); }
    };
    async function refresh() {
      if (disposed) return;
      const id = ++generation;
      if (aborter) aborter.abort();
      const abort = new AbortController(); aborter = abort;
      let timer;
      recheck();
      try {
        const request = (async () => { const r = await fetcher(url,{cache:'no-store',signal:abort.signal}); if (!r.ok) throw Error(`HTTP ${r.status}`); const c = await r.json(); if (!c || typeof c !== 'object' || Array.isArray(c)) throw Error('Malformed safety record'); return c; })();
        const expiry = new Promise((_,reject) => { timer = setTimeout(() => { abort.abort(); reject(Error('Safety request timed out')); },timeoutMs); });
        const c = await Promise.race([request,expiry]);
        if (disposed || id !== generation) return;
        snapshot = c; failure = null;
      } catch (error) {
        if (disposed || id !== generation) return;
        // Do not preserve a current-looking flag or positive badge after a failed refresh.
        snapshot = null; failure = String(error);
      } finally {
        clearTimeout(timer);
        if (!disposed && id === generation) recheck();
      }
    }
    return {refresh,recheck,destroy() { disposed = true; ++generation; aborter?.abort(); }};
  }
  function text(id,value) { const node = document.getElementById(id); if (node) node.textContent = value || ''; }
  function link(id,value) { const node = document.getElementById(id), url = safeUrl(value); if (!node) return; if (url) node.href = url; else node.removeAttribute('href'); }
  function renderPole(pole,state) {
    if (!pole) return;
    pole.replaceChildren(); pole.className = 'flagpole';
    pole.removeAttribute('aria-label'); pole.removeAttribute('role'); pole.hidden = true;
    if (state.status !== 'current') return;
    const colors = state.primary === 'Double Red' ? ['var(--red)','var(--red)'] : state.primary ? [state.primary === 'Green' ? 'var(--good)' : state.primary === 'Yellow' ? 'var(--yellow)' : 'var(--red)'] : [];
    if (state.purple) colors.push('var(--purple)');
    colors.forEach((color,i) => { const shape = document.createElement('span'); shape.className = 'flagshape'; shape.style.top = `${5 + i * 31}px`; shape.style.background = color; shape.setAttribute('aria-hidden','true'); pole.appendChild(shape); });
    pole.style.height = colors.length >= 3 ? '106px' : colors.length === 2 ? '82px' : '70px';
    pole.hidden = false; pole.setAttribute('role','img'); pole.setAttribute('aria-label',`Current beach flag: ${state.label}`);
  }
  function render(state) {
    const c = state.record;
    const heading = document.getElementById('currentFlag') || document.getElementById('currentStatus');
    if (!heading) return;
    heading.textContent = state.title;
    const card = heading.closest('.flag-card,.flag-card-wide') || heading.parentElement;
    card.dataset.safetyState = state.status; card.setAttribute('aria-live','polite'); card.setAttribute('aria-atomic','true');
    const eyebrow = card.querySelector('.eyebrow'); if (eyebrow) eyebrow.textContent = 'Beach flag evidence';
    let provenance = card.querySelector('.ktg-evidence-source');
    if (!provenance) { provenance = document.createElement('p'); provenance.className = 'ktg-evidence-source small'; heading.insertAdjacentElement('afterend',provenance); }
    provenance.replaceChildren();
    const sourceHref = safeUrl(c.source_url);
    if (c.source_name && sourceHref) { const a = document.createElement('a'); a.href = sourceHref; a.textContent = c.source_name; a.target = '_blank'; a.rel = 'noopener'; provenance.append('Displayed evidence source: ',a); }
    else provenance.textContent = 'Displayed evidence source unavailable.';
    text('currentMeaning',state.meaning);
    renderPole(document.getElementById('flagPole'),state);
    const fresh = document.getElementById('flagFreshness') || document.getElementById('statusFreshness');
    if (fresh) {
      fresh.className = 'status flag-status' + (state.status === 'current' || state.status === 'no_explicit_flag' ? '' : ' stale');
      const stamp = state.stamp ? `Evidence time: ${state.stamp}. ` : '';
      const checked = state.checkedAt ? `Source checked: ${state.checkedAt}. ` : '';
      fresh.textContent = stamp + checked + state.confidenceText + ' Posted flags and lifeguards control.';
    }
    let badge = card.querySelector('.ktg-confidence');
    if (!badge) { badge = document.createElement('div'); badge.className = 'ktg-confidence'; card.appendChild(badge); }
    badge.className = 'ktg-confidence ktg-confidence-' + (state.confidence === 'corroborated' ? 'good' : ['source_disagreement','conflict'].includes(state.confidence) ? 'alert' : 'neutral');
    badge.textContent = state.confidenceText; badge.dataset.confidence = state.confidence;
    text('authority',c.official_authority); text('sourceSystem',c.source_name); text('methodNote',c.update_note || c.method); text('safetyNote',c.safety_note || 'Posted flags and lifeguard instructions control. Weather and forecasts never determine the flag.');
    if (c.source_url) link('sourceLink',c.source_url);
    if (c.official_authority_url) link('officialLink',c.official_authority_url);
    const beaches = document.getElementById('beachList');
    if (beaches && Array.isArray(c.beaches)) { beaches.replaceChildren(); c.beaches.forEach(name => { const li = document.createElement('li'); li.textContent = String(name); beaches.appendChild(li); }); }
    const source = document.getElementById('sourceDisclosure');
    if (source) {
      source.replaceChildren();
      for (const [name,value,url] of [['Source',c.source_name,c.source_url],['Authority',c.official_authority,c.official_authority_url]]) {
        if (!value) continue;
        const p = document.createElement('p'), a = document.createElement('a'); p.append(`${name}: `); a.textContent = value;
        const href = safeUrl(url); if (href) { a.href = href; a.target = '_blank'; a.rel = 'noopener'; }
        p.appendChild(a); source.appendChild(p);
      }
      const method = document.createElement('p'); method.textContent = c.method || 'Use the official local source and posted beach flags.'; source.appendChild(method);
    }
  }
  function start() {
    const ready = () => {
      const path = (location.pathname.replace(/index\.html$/,'').replace(/\/+$/,'') || '') + '/';
      const url = PATHS[path]; if (!url || !Safety) return;
      const controllers = [];
      const primary = createController({url,render}); controllers.push(primary);
      const east = document.querySelector('[data-east-location]'), related = document.getElementById('relatedFlags');
      if (east && related) {
        for (const slug of (east.dataset.related || '').split(',').filter(x => /^[a-z0-9-]+$/.test(x))) {
          const box = document.createElement('div'); box.className = 'card'; box.setAttribute('aria-live','polite'); related.appendChild(box);
          controllers.push(createController({url:`/data/${slug}/current_flag.json`,render:state => { box.replaceChildren(); const name = document.createElement('div'), h = document.createElement('h3'), p = document.createElement('p'); name.textContent = state.record.location || slug.replaceAll('-',' '); h.textContent = state.title; p.textContent = state.confidenceText + (state.stamp ? ` Evidence time: ${state.stamp}.` : ''); box.append(name,h,p); const href = safeUrl(state.record.official_authority_url); if (href) { const a = document.createElement('a'); a.href = href; a.textContent = 'Official safety source'; box.appendChild(a); } }}));
        }
      }
      controllers.forEach(c => c.refresh());
      // Re-evaluate on wall-clock ticks and resume. Persisted fresh=true is never trusted.
      const aging = setInterval(() => controllers.forEach(c => c.recheck()),1000);
      const polling = setInterval(() => controllers.forEach(c => c.refresh()),60000);
      document.addEventListener('visibilitychange',() => { controllers.forEach(c => c.recheck()); if (!document.hidden) controllers.forEach(c => c.refresh()); });
      window.addEventListener('pageshow',() => controllers.forEach(c => c.recheck()));
      window.addEventListener('pagehide',event => { if (!event.persisted) { clearInterval(aging); clearInterval(polling); controllers.forEach(c => c.destroy()); } });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',ready,{once:true}); else ready();
  }
  return {PATHS,safeUrl,createController,renderPole,start};
});
