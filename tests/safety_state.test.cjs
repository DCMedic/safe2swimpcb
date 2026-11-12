const {test} = require('node:test');
const assert = require('node:assert/strict');
const S = require('../assets/safety-state.js');
const UI = require('../assets/safety-ui.js');
const now = Date.parse('2026-11-11T12:00:00Z');
const record = extra => ({flag:'Green',last_verified_at:'2026-11-11T11:00:00Z',last_checked_at:'2026-11-11T11:30:00Z',stale_after_hours:2,source_check_status:'verified',source_name:'County lifeguards',source_url:'https://example.org/current',...extra});
const secondary = extra => ({source_lineage:'visitbeaches',flag:'Green',report_at:'2026-11-11T11:00:00Z',freshness_hours:2,...extra});
test('TTL and timestamps fail closed, including exact expiry and future', () => {
  for (const ttl of [undefined,null,0,-1,NaN,Infinity,25,'24',true]) assert.equal(S.derive(record({stale_after_hours:ttl}),now).status,'stale');
  for (const stamp of [undefined,null,'broken','2026-11-11','2026-11-11T11:00:00','2026-02-30T11:00:00Z','2026-11-11T24:00:00Z','2026-11-11T12:00:01Z']) assert.equal(S.derive(record({last_verified_at:stamp}),now).status,'stale');
  assert.equal(S.derive(record({last_verified_at:'2026-11-11T10:00:00Z'}),now).status,'stale');
});
test('check time never rejuvenates observation, even invalid/null', () => {
  for (const stamp of [null,'broken','2026-11-10T12:00:00Z']) assert.equal(S.derive(record({observed_at:stamp}),now).status,'stale');
  assert.equal(S.derive(record({source_check_status:'failed'}),now).status,'stale');
});
test('confidence ages independently and cached enums are ignored', () => {
  assert.equal(S.derive(record({visitbeaches_evidence:secondary()}),now).confidence,'corroborated');
  for (const evidence of [secondary({report_at:'2026-11-10T00:00:00Z'}),secondary({freshness_hours:undefined}),secondary({report_at:'2026-11-12T00:00:00Z'})]) assert.equal(S.derive(record({visitbeaches_evidence:evidence,multi_source_confidence:'corroborated'}),now).confidence,'primary_only');
});
test('source lineage never corroborates itself', () => {
  for (const source of [{source_lineage:'visitbeaches'},{source_name:'VisitBeaches'},{source_url:'https://visitbeaches.org/map'},{source_lineage:'other',provenance_tier:'primary_visitbeaches_ambassador_gap_fill'}]) assert.equal(S.derive(record({...source,visitbeaches_evidence:secondary()}),now).confidence,'single_source');
});
test('aliases, conflicting structured flags, Purple and closure', () => {
  assert.equal(S.derive(record({flag:'Single Red',visitbeaches_evidence:secondary({flag:'Red'})}),now).confidence,'corroborated');
  const state = S.derive(record({flag:'Double Red',purple:true}),now); assert.equal(state.label,'Double Red + Purple'); assert.match(state.meaning,/Water closed/);
  assert.equal(S.derive(record({primary_flag:'Green',flag:'Double Red'}),now).status,'conflict');
  assert.equal(S.derive(record({visitbeaches_evidence:secondary({primary_flag:'Green',flag:'Double Red'})}),now).confidence,'conflict');
  assert.equal(S.derive(record({flag:'Purple'}),now).label,'Purple');
  assert.equal(S.derive(record({flag:'Safe',label:'Green'}),now).status,'unavailable');
});
test('no-explicit flag requires a fresh successful check, not green', () => {
  const state = S.derive(record({flag:null,purple:false}),now); assert.equal(state.status,'no_explicit_flag'); assert.equal(state.primary,null);
  assert.equal(S.derive(record({flag:null,last_checked_at:'2026-11-10T00:00:00Z'}),now).status,'unavailable');
});
test('latest request wins; failure clears old positive state; expiry without refetch', async () => {
  let time = now, pending = [], states = [];
  const ctl = UI.createController({url:'/fixture',clock:()=>time,render:s=>states.push(s),fetcher:()=>new Promise((resolve,reject)=>pending.push({resolve,reject})),timeoutMs:100});
  const first=ctl.refresh(), second=ctl.refresh();
  pending[1].resolve({ok:true,json:async()=>record({flag:'Double Red'})}); await second;
  pending[0].resolve({ok:true,json:async()=>record({flag:'Green'})}); await first;
  assert.equal(states.at(-1).primary,'Double Red');
  time += 2*36e5; ctl.recheck(); assert.equal(states.at(-1).status,'stale');
  const third=ctl.refresh(); pending[2].reject(Error('offline')); await third;
  assert.equal(states.at(-1).status,'unavailable'); assert.equal(states.at(-1).primary,null);
  ctl.destroy();
});
test('timeout and malformed payload fail closed', async () => {
  for (const fetcher of [()=>new Promise(()=>{}),async()=>({ok:true,json:async()=>[]})]) {
    let state; const ctl=UI.createController({url:'/fixture',clock:()=>now,render:s=>state=s,fetcher,timeoutMs:5}); await ctl.refresh(); assert.equal(state.status,'unavailable'); ctl.destroy();
  }
});

test('Python and JavaScript share timestamp, TTL, alias and lineage fixtures', () => {
  const fixtures=require('./fixtures/source_evidence.json');
  for (const x of fixtures.freshness) assert.equal(S.freshness(x.stamp,x.hours,Date.parse(fixtures.now)).fresh,x.fresh,JSON.stringify(x));
  for (const x of fixtures.flags) assert.equal(S.canonicalFlag(x.input),x.canonical);
  for (const x of fixtures.observations) assert.equal(S.observationStamp(x.record) ?? null,x.stamp);
  for (const x of fixtures.lineages) assert.equal(S.lineage(x.record)==='visitbeaches',x.visitbeaches);
});

test('malformed flag containers and image/text conflict fail closed', () => {
  for (const flag of [['Green'],['Double Red'],{},true,1]) assert.equal(S.derive(record({flag}),now).status,'unavailable');
  assert.equal(S.derive(record({evidence_conflict:true}),now).status,'conflict');
});

test('missing provenance, unverified checks and textual conflicts never claim current', () => {
  for (const patch of [{source_url:null},{source_name:''},{source_check_status:undefined}]) assert.notEqual(S.derive(record(patch),now).status,'current');
  assert.equal(S.derive(record({evidence_conflict:'semantic=Green; image=Double Red'}),now).status,'conflict');
  assert.equal(S.derive(record({visitbeaches_evidence:secondary({source_lineage:null})}),now).confidence,'primary_only');
});
test('pole has exact closure/Purple geometry and loses all current cues on failure', () => {
  const node = () => ({children:[],style:{},attrs:{},replaceChildren(){this.children=[];},appendChild(child){this.children.push(child);},setAttribute(key,value){this.attrs[key]=value;},removeAttribute(key){delete this.attrs[key];}});
  global.document = {createElement:node};
  const pole=node(); UI.renderPole(pole,S.derive(record({flag:'Double Red',purple:true}),now));
  assert.equal(pole.children.length,3); assert.equal(pole.attrs['aria-label'],'Current beach flag: Double Red + Purple'); assert.equal(pole.hidden,false);
  UI.renderPole(pole,S.derive(null,now,'offline')); assert.equal(pole.children.length,0); assert.equal(pole.hidden,true); assert.equal(pole.attrs['aria-label'],undefined);
  delete global.document;
});
test('unchanged clock ticks do not repeatedly announce the live safety card', async () => {
  let renders=0; const ctl=UI.createController({url:'/fixture',clock:()=>now,render:()=>renders++,fetcher:async()=>({ok:true,json:async()=>record()})});
  await ctl.refresh(); const count=renders; ctl.recheck();ctl.recheck(); assert.equal(renders,count); ctl.destroy();
});
