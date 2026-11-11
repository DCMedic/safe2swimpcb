/* Shared, clock-dependent safety contract. No DOM, network or producer freshness booleans. */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.KTGSafety = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  const MAX_HOURS = 24;
  const MEANINGS = {Green:'Low hazard. Exercise caution.', Yellow:'Medium hazard. Moderate surf and/or currents.', Red:'High hazard. High surf and/or strong currents.', 'Double Red':'Water closed to the public.'};
  const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  function canonicalFlag(value) {
    if (typeof value !== 'string') return null;
    if (value === 'Single Red') return 'Red';
    return Object.hasOwn(MEANINGS, value) ? value : null;
  }
  function timestamp(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
    const day = value.slice(0,10), date = new Date(day + 'T00:00:00Z');
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0,10) !== day) return null;
    const parts = value.slice(11,19).split(':').map(Number);
    if (parts[0] > 23 || parts[1] > 59 || parts[2] > 59) return null;
    const ms = Date.parse(value);
    return Number.isFinite(ms) ? ms : null;
  }
  function freshness(stamp, hours, now = Date.now()) {
    const time = timestamp(stamp);
    const validLimit = typeof hours === 'number' && Number.isFinite(hours) && hours > 0 && hours <= MAX_HOURS;
    const validTime = time !== null && Number.isFinite(now) && time <= now;
    return {fresh:validTime && validLimit && now < time + hours * 36e5, time, expiresAt:validTime && validLimit ? time + hours * 36e5 : null};
  }
  function lineage(c) {
    if (['source_lineage','provenance_tier','source_name'].some(key => /visitbeaches/i.test(String(c[key] || '')))) return 'visitbeaches';
    for (const value of [c.source_data_url,c.source_url]) {
      try { const host = new URL(value).hostname.toLowerCase(); if (host === 'visitbeaches.org' || host.endsWith('.visitbeaches.org')) return 'visitbeaches'; } catch (_) { /* invalid URL is not provenance */ }
    }
    return c.source_lineage || null;
  }
  function flagState(c) {
    const a = c.primary_flag, b = c.flag;
    const invalid = [a,b].some(v => v != null && v !== '' && v !== 'Purple' && !canonicalFlag(v));
    const primary = canonicalFlag(a) || canonicalFlag(b);
    const conflict = Boolean(canonicalFlag(a) && canonicalFlag(b) && canonicalFlag(a) !== canonicalFlag(b));
    return {primary, purple:c.purple === true || a === 'Purple' || b === 'Purple', invalid, conflict};
  }
  function observationStamp(c) {
    // A supplied observation timestamp is authoritative even if malformed. Never rejuvenate it with a poll timestamp.
    for (const key of ['observed_at','official_updated_at']) if (Object.hasOwn(c,key)) return c[key];
    return c.last_verified_at;
  }
  function derive(record, now = Date.now(), error = null) {
    const c = isRecord(record) ? record : {};
    const f = flagState(c), stamp = observationStamp(c), age = freshness(stamp,c.stale_after_hours,now);
    const hasFlag = Boolean(f.primary || f.purple);
    const evidence = isRecord(c.visitbeaches_evidence) ? c.visitbeaches_evidence : {};
    const secondary = flagState(evidence), secondaryAge = freshness(evidence.report_at,evidence.freshness_hours,now);
    let sourceUrl = null;
    try { const url = new URL(c.source_url); if (['https:','http:'].includes(url.protocol)) sourceUrl = url.href; } catch (_) { /* missing or invalid source identity */ }
    const hasSource = Boolean(sourceUrl && typeof c.source_name === 'string' && c.source_name.trim());
    const checkFailed = c.source_reachable === false || c.source_check_status !== 'verified';
    const primaryConflict = f.conflict || Boolean(c.evidence_conflict) || c.visitbeaches_flag_conflict === true || c.flag_conflict === true;
    let status = error ? 'unavailable' : primaryConflict ? 'conflict' : f.invalid || !hasSource ? 'unavailable' : hasFlag ? (age.fresh && !checkFailed ? 'current' : 'stale') : 'unavailable';
    const checkAge = freshness(Object.hasOwn(c,'last_checked_at') ? c.last_checked_at : c.last_verified_at,c.stale_after_hours,now);
    if (!error && !primaryConflict && !f.invalid && hasSource && !hasFlag && !checkFailed && c.source_check_status === 'verified' && checkAge.fresh) status = 'no_explicit_flag';
    const label = [f.primary,f.purple ? 'Purple' : null].filter(Boolean).join(' + ');
    let title = status === 'current' ? label : status === 'stale' ? `Last verified flag: ${label}` : status === 'conflict' ? 'Conflicting flag reports. Check your beach.' : status === 'no_explicit_flag' ? 'Source checked. No explicit flag published.' : 'Current flag unavailable. Check the official source.';
    let confidence = 'unavailable', confidenceText = 'Current evidence could not be verified.';
    if (status === 'current') {
      confidence = lineage(c) === 'visitbeaches' ? 'single_source' : 'primary_only';
      confidenceText = confidence === 'single_source' ? 'Single source: Beach Ambassador report. No independent corroboration.' : 'Verified primary source. No fresh independent corroboration.';
      if (lineage(c) !== 'visitbeaches' && lineage(evidence) === 'visitbeaches' && secondaryAge.fresh && !secondary.invalid) {
        if (evidence.flag_conflict === true || secondary.conflict) { confidence = 'conflict'; confidenceText = 'Secondary reports conflict. The local authority remains primary. Check posted flags.'; }
        else if (secondary.primary || secondary.purple) {
          if (f.primary !== secondary.primary) { confidence = 'source_disagreement'; confidenceText = 'Fresh sources disagree. The local authority remains primary. Check posted flags.'; }
          else if (f.purple !== secondary.purple) { confidence = 'partial_corroboration'; confidenceText = 'Primary flag agrees across sources; Purple reporting differs.'; }
          else { confidence = 'corroborated'; confidenceText = 'Independent primary and Beach Ambassador reports agree.'; }
        }
      }
    } else if (status === 'stale') confidenceText = 'Last verified evidence only. This is not a current-status claim.';
    else if (status === 'conflict') confidenceText = 'Reports disagree. No single regional flag is asserted.';
    else if (status === 'no_explicit_flag') confidenceText = 'Source reachability is not evidence of safe swimming conditions.';
    const meaning = status === 'current' ? [MEANINGS[f.primary],f.purple ? 'Purple: dangerous marine life.' : null].filter(Boolean).join(' ') : 'Follow posted flags and lifeguard instructions. Verify conditions before entering the water.';
    return {status,title,label,primary:f.primary,purple:f.purple,meaning,confidence,confidenceText,stamp:timestamp(stamp) !== null ? stamp : null,checkedAt:timestamp(c.last_checked_at) !== null ? c.last_checked_at : null,expiresAt:age.expiresAt,record:c};
  }
  return {MAX_HOURS,canonicalFlag,timestamp,freshness,lineage,flagState,observationStamp,derive};
});
