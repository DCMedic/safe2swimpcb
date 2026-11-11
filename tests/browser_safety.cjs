/* Deterministic local browser checks. Requires playwright and Chromium; no live requests. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(process.env.SITE_ROOT || path.join(__dirname,'..'));
const now = Date.parse('2026-11-11T12:00:00Z');
const base = {flag:'Double Red',purple:true,last_verified_at:'2026-11-11T11:00:00Z',last_checked_at:'2026-11-11T11:30:00Z',stale_after_hours:2,source_name:'County lifeguards',source_url:'https://example.org/current',source_check_status:'verified',visitbeaches_evidence:{source_lineage:'visitbeaches',flag:'Double Red',purple:true,report_at:'2026-11-11T11:00:00Z',freshness_hours:1.01}};
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',args:['--no-sandbox']});
  let checks=0;
  try {
    for (const route of ['/','/destin/','/cape-san-blas/','/siesta-key/']) {
      const context=await browser.newContext({viewport:{width:390,height:844}}), page=await context.newPage();
      let fail=false, requests=0;
      await page.addInitScript(t=>{window.__testNow=t; Date.now=()=>window.__testNow;},now);
      await page.route('**/*',async r=>{
        const url=new URL(r.request().url());
        if(url.hostname!=='127.0.0.1') return r.abort();
        if(url.pathname.startsWith('/data/')) {
          if(url.pathname.endsWith('/current_flag.json')) {requests++; return r.fulfill({status:fail?503:200,contentType:'application/json',body:JSON.stringify(base)});}
          return r.fulfill({status:404,body:'No fixture'});
        }
        const file=path.join(root,url.pathname.endsWith('/')?url.pathname+'index.html':url.pathname);
        if (!file.startsWith(root) || !fs.existsSync(file)) return r.fulfill({status:404,body:'missing'});
        return r.fulfill({path:file});
      });
      await page.goto('http://127.0.0.1'+route);
      const heading=page.locator('#currentFlag,#currentStatus');
      await heading.filter({hasText:'Double Red + Purple'}).waitFor();
      assert.equal(await page.locator('#flagPole .flagshape').count(),3); checks++;
      assert.equal(await page.locator('#flagPole').getAttribute('aria-label'),'Current beach flag: Double Red + Purple'); checks++;
      assert.equal(await page.locator('.ktg-confidence').getAttribute('data-confidence'),'corroborated'); checks++;
      assert.match(await page.locator('.ktg-evidence-source').textContent(),/Displayed evidence source: County lifeguards/); checks++;
      assert.equal(await heading.evaluate(e=>e.closest('.flag-card,.flag-card-wide').getAttribute('aria-live')),'polite'); checks++;
      await page.evaluate(t=>window.__testNow=t,now+2*60000); await page.waitForTimeout(1100);
      assert.equal(await page.locator('.ktg-confidence').getAttribute('data-confidence'),'primary_only'); checks++;
      await page.evaluate(t=>window.__testNow=t,now+2*36e5); await page.waitForTimeout(1100);
      assert.match(await heading.textContent(),/^Last verified flag:/); assert.equal(await page.locator('#flagPole').isVisible(),false); checks+=2;
      // Only the canonical controller requests safety JSON. Related east cards are separate validated snapshots.
      assert.equal(requests,route==='/cape-san-blas/'?3:1); checks++;
      fail=true; await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
      await heading.filter({hasText:'Current flag unavailable'}).waitFor();
      assert.equal(await page.locator('#flagPole .flagshape').count(),0); checks++;
      assert.equal(await page.locator('.ktg-confidence').getAttribute('data-confidence'),'unavailable'); checks++;
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true); checks++;
      await context.close();
    }
    const context=await browser.newContext({javaScriptEnabled:false}); const page=await context.newPage();
    await page.route('**/*',r=>{const url=new URL(r.request().url()); if(url.hostname!=='127.0.0.1') return r.abort(); const file=path.join(root,url.pathname==='/'?'index.html':url.pathname); return fs.existsSync(file)?r.fulfill({path:file}):r.fulfill({status:404,body:''});});
    await page.goto('http://127.0.0.1/'); assert.equal(await page.locator('#flagPole').isVisible(),false); checks++;
    await context.close();
    console.log(`Browser safety: ${checks} assertions passed across PCB, Western, Eastern, Southwest and no-JavaScript pages.`);
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
