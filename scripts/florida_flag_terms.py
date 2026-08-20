#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass

PRIMARY_SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Double Red": 4}


@dataclass(frozen=True)
class FloridaFlagState:
    primary: str | None = None
    purple: bool = False
    primary_term: str | None = None
    purple_term: str | None = None

    @property
    def label(self) -> str | None:
        if self.primary and self.purple:
            return f"{self.primary} + Purple"
        if self.primary:
            return self.primary
        if self.purple:
            return "Purple"
        return None

    @property
    def severity(self) -> int | None:
        return PRIMARY_SEVERITY.get(self.primary)


def _clean(value: object) -> str:
    text = str(value or "").replace("&", " and ")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def interpret_florida_flag_terms(value: object) -> FloridaFlagState:
    """Interpret explicit Florida Beach Warning Flag terminology.

    This function maps standardized *condition language*, not forecast risk.
    For example, "High Hazard" maps to Red, while "High rip current risk"
    deliberately does not. Purple is independent and can accompany a primary
    surf-condition flag.
    """
    text = _clean(value)
    if not text:
        return FloridaFlagState()

    primary = None
    primary_term = None

    double_red_patterns = (
        r"\bdouble\s+red(?:\s+flag)?\b",
        r"\btwo\s+red\s+flags?\b",
        r"\bwater\s+closed(?:\s+to\s+(?:the\s+)?public)?\b",
    )
    red_patterns = (
        r"\bsingle\s+red(?:\s+flag)?\b",
        r"\bred\s+flag\b",
        r"\bhigh\s+hazard\b",
        r"\bhigh\s+surf\s+(?:and|and/or|or)\s+currents?\b",
    )
    yellow_patterns = (
        r"\byellow\s+flag\b",
        r"\bmedium\s+hazard\b",
        r"\bmoderate\s+hazard\b",
        r"\bmoderate\s+surf\s+(?:and|and/or|or)\s+currents?\b",
    )
    green_patterns = (
        r"\bgreen\s+flag\b",
        r"\blow\s+hazard\b",
        r"\bcalm\s+conditions(?:\s*,?\s*exercise\s+caution)?\b",
    )

    for label, patterns in (
        ("Double Red", double_red_patterns),
        ("Red", red_patterns),
        ("Yellow", yellow_patterns),
        ("Green", green_patterns),
    ):
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                primary = label
                primary_term = match.group(0)
                break
        if primary:
            break

    purple_match = re.search(
        r"\b(?:purple\s+flag|dangerous\s+marine\s+life)\b",
        text,
        re.I,
    )

    return FloridaFlagState(
        primary=primary,
        purple=bool(purple_match),
        primary_term=primary_term,
        purple_term=purple_match.group(0) if purple_match else None,
    )


def primary_flag(value: object) -> str | None:
    return interpret_florida_flag_terms(value).primary


def has_dangerous_marine_life(value: object) -> bool:
    return interpret_florida_flag_terms(value).purple
