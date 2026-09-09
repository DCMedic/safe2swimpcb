#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

GRAPHQL_URL = "https://api.visitbeaches.org/graphql"
USER_AGENT = "KnowTheGulf/1.0 (+https://knowthegulf.com)"

SEARCH_QUERY = r'''
query SearchBeaches($search: String!) {
  searchBeaches(search: $search) {
    id
    name
    location
    latitude
    longitude
    city { name state { name abbreviation } }
  }
}
'''

BEACH_QUERY = r'''
query GetBeach($id: ID!) {
  beach(id: $id) {
    id
    name
    location
    latitude
    longitude
    city { name state { name abbreviation } }
    lastThreeDaysOfReports {
      id
      createdAt
      latitude
      longitude
      user { id name }
      beachReport {
        parameterCategory { id name slug }
        reportParameters {
          parameter {
            id
            name
            prompt
            description
            unit
            type
            parameterCategory { id name slug }
          }
          parameterValues { id name description value imagePath icon }
          value
        }
      }
    }
  }
}
'''

FLAG_RE = re.compile(r"\b(green|yellow|red|double\s+red|two\s+red|water\s+closed)\b", re.I)
PURPLE_RE = re.compile(r"\b(purple|dangerous\s+marine\s+life|marine\s+life)\b", re.I)


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_flag(value: Any) -> str | None:
    text = re.sub(r"[^a-z ]+", " ", _norm_text(value).lower())
    if re.search(r"\bdouble\s+red\b|\btwo\s+red\b|\bwater\s+closed\b", text):
        return "Double Red"
    if re.search(r"\bred\b", text):
        return "Red"
    if re.search(r"\byellow\b|\bmoderate\b|\bmedium\b", text):
        return "Yellow"
    if re.search(r"\bgreen\b|\blow\s+hazard\b", text):
        return "Green"
    return None


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parameter_text(param: dict) -> str:
    parameter = param.get("parameter") or {}
    category = parameter.get("parameterCategory") or {}
    pieces = [
        parameter.get("name"), parameter.get("prompt"), parameter.get("description"),
        category.get("name"), category.get("slug"), param.get("value"),
    ]
    for pv in param.get("parameterValues") or []:
        pieces.extend([pv.get("name"), pv.get("description"), pv.get("value")])
    return " | ".join(_norm_text(x) for x in pieces if x not in (None, ""))


def _parameter_key(param: dict) -> str:
    parameter = param.get("parameter") or {}
    category = parameter.get("parameterCategory") or {}
    return " ".join(_norm_text(x).lower() for x in (
        parameter.get("name"), parameter.get("prompt"), category.get("name"), category.get("slug")
    ) if x)


def normalize_report(report: dict) -> dict:
    raw_params: list[dict] = []
    flag: str | None = None
    purple = False
    normalized: dict[str, Any] = {}

    beach_report = report.get("beachReport") or {}
    for category_block in beach_report if isinstance(beach_report, list) else [beach_report]:
        if not isinstance(category_block, dict):
            continue
        outer_category = category_block.get("parameterCategory") or {}
        for rp in category_block.get("reportParameters") or []:
            if not isinstance(rp, dict):
                continue
            p = rp.get("parameter") or {}
            cat = p.get("parameterCategory") or outer_category or {}
            values = rp.get("parameterValues") or []
            entry = {
                "parameter_id": p.get("id"),
                "parameter": p.get("name"),
                "prompt": p.get("prompt"),
                "unit": p.get("unit"),
                "category": cat.get("name"),
                "category_slug": cat.get("slug"),
                "value": rp.get("value"),
                "selected_values": [
                    {"id": v.get("id"), "name": v.get("name"), "value": v.get("value"), "description": v.get("description")}
                    for v in values if isinstance(v, dict)
                ],
            }
            raw_params.append(entry)

            text = _parameter_text(rp)
            key = _parameter_key(rp)
            value_names = " | ".join(_norm_text(v.get("name")) for v in values if isinstance(v, dict))

            # A warning flag is accepted only when the parameter/category itself is flag-like,
            # or the selected value explicitly says "X Flag"/"Water Closed". This prevents
            # unrelated colors or generic hazard text from becoming a Florida warning flag.
            flag_context = "flag" in key or bool(re.search(r"\b(?:green|yellow|red|purple|double\s+red)\s+flag\b|water\s+closed", value_names, re.I))
            if flag_context:
                candidate = normalize_flag(value_names or rp.get("value") or text)
                if candidate:
                    flag = candidate
                if PURPLE_RE.search(value_names + " | " + text):
                    purple = True

            if "dangerous marine life" in key or "marine life" in key or "purple flag" in key:
                if PURPLE_RE.search(text) or any(str(v.get("value", "")).lower() in {"1", "true", "yes"} for v in values if isinstance(v, dict)):
                    purple = True

            # Preserve a useful normalized view while retaining the complete raw parameter set.
            low = key
            scalar = rp.get("value")
            selected = [v.get("name") for v in values if isinstance(v, dict) and v.get("name")]
            display_value: Any = scalar if scalar not in (None, "") else (selected[0] if len(selected) == 1 else selected or None)
            if "water temperature" in low or ("temperature" in low and "water" in low):
                normalized["water_temperature"] = {"value": display_value, "unit": p.get("unit")}
            elif "surf" in low or "wave" in low:
                normalized.setdefault("surf", []).append({"parameter": p.get("name"), "value": display_value, "unit": p.get("unit")})
            elif "wind" in low:
                normalized.setdefault("wind", []).append({"parameter": p.get("name"), "value": display_value, "unit": p.get("unit")})
            elif "respiratory" in low:
                normalized["respiratory_irritation"] = display_value
            elif "dead fish" in low or "fish kill" in low:
                normalized["dead_fish"] = display_value
            elif "water color" in low or "water colour" in low:
                normalized["water_color"] = display_value
            elif "crowd" in low:
                normalized["crowd"] = display_value

    return {
        "report_id": report.get("id"),
        "created_at": report.get("createdAt"),
        "latitude": report.get("latitude"),
        "longitude": report.get("longitude"),
        "ambassador": report.get("user"),
        "flag": flag,
        "purple": purple,
        "normalized_conditions": normalized,
        "parameters": raw_params,
    }


@dataclass
class VisitBeachesClient:
    session: requests.Session

    @classmethod
    def create(cls) -> "VisitBeachesClient":
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        return cls(s)

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        r = self.session.post(GRAPHQL_URL, json={"query": query, "variables": variables or {}}, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"VisitBeaches GraphQL error: {payload['errors']}")
        return payload.get("data") or {}

    def search_beaches(self, search: str) -> list[dict]:
        return self.graphql(SEARCH_QUERY, {"search": search}).get("searchBeaches") or []

    def beach(self, beach_id: str) -> dict | None:
        return self.graphql(BEACH_QUERY, {"id": beach_id}).get("beach")


def _candidate_score(candidate: dict, alias: str) -> tuple[int, int]:
    name = _norm_text(candidate.get("name")).lower()
    target = _norm_text(alias).lower()
    if name == target:
        return (3, -len(name))
    if target in name or name in target:
        return (2, -abs(len(name) - len(target)))
    target_tokens = {x for x in re.split(r"\W+", target) if len(x) > 2}
    name_tokens = {x for x in re.split(r"\W+", name) if len(x) > 2}
    overlap = len(target_tokens & name_tokens)
    return (1 if overlap else 0, overlap)


def resolve_aliases(client: VisitBeachesClient, aliases: list[str]) -> list[dict]:
    resolved: dict[str, dict] = {}
    for alias in aliases:
        candidates = client.search_beaches(alias)
        ranked = sorted(candidates, key=lambda c: _candidate_score(c, alias), reverse=True)
        if ranked and _candidate_score(ranked[0], alias)[0] >= 2:
            c = ranked[0]
            resolved[str(c.get("id"))] = c
    return list(resolved.values())


def collect_location(aliases: list[str], *, freshness_hours: float = 24.0, client: VisitBeachesClient | None = None) -> dict:
    client = client or VisitBeachesClient.create()
    checked_at = datetime.now(timezone.utc)
    matches = resolve_aliases(client, aliases)
    observations: list[dict] = []

    for match in matches:
        beach = client.beach(str(match["id"]))
        if not beach:
            continue
        for report in beach.get("lastThreeDaysOfReports") or []:
            nr = normalize_report(report)
            stamp = parse_time(nr.get("created_at"))
            age_h = ((checked_at - stamp).total_seconds() / 3600.0) if stamp else None
            nr.update({
                "beach_id": beach.get("id"),
                "beach_name": beach.get("name"),
                "beach_location": beach.get("location"),
                "beach_latitude": beach.get("latitude"),
                "beach_longitude": beach.get("longitude"),
                "age_hours": round(age_h, 3) if age_h is not None else None,
                "fresh": age_h is not None and -0.25 <= age_h <= freshness_hours,
                "source_class": "Beach Ambassador Report",
            })
            observations.append(nr)

    observations.sort(key=lambda x: parse_time(x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    fresh = [o for o in observations if o.get("fresh")]
    fresh_flags = [o for o in fresh if o.get("flag")]
    distinct_flags = sorted({o["flag"] for o in fresh_flags})

    selected_flag: str | None = None
    conflict = False
    if len(distinct_flags) == 1:
        selected_flag = distinct_flags[0]
    elif len(distinct_flags) > 1:
        conflict = True

    # Purple is an overlay. Preserve it only from fresh observations. If no fresh
    # report exists, the newest report remains available as last-known evidence.
    purple = any(bool(o.get("purple")) for o in fresh)
    newest = observations[0] if observations else None
    newest_flag = next((o for o in observations if o.get("flag")), None)

    return {
        "source": "Mote Marine Laboratory Beach Conditions Reporting System / VisitBeaches",
        "source_url": "https://visitbeaches.org/map",
        "source_data_url": GRAPHQL_URL,
        "source_class": "Beach Ambassador Reports only; Community Reports excluded",
        "checked_at": checked_at.isoformat(),
        "freshness_hours": freshness_hours,
        "aliases": aliases,
        "matched_beaches": matches,
        "observations": observations,
        "fresh_observation_count": len(fresh),
        "flag": selected_flag,
        "purple": purple,
        "flag_conflict": conflict,
        "fresh_distinct_flags": distinct_flags,
        "newest_report_at": newest.get("created_at") if newest else None,
        "newest_flag_report": newest_flag,
        "selection_rule": "A regional flag is emitted only when all fresh Ambassador observations with explicit flags agree. Conflicting fresh flags remain separate observations and no regional flag is emitted.",
    }
