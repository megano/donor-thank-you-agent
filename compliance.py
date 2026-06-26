"""Pluggable compliance profiles.

The donor pipeline is gift-agnostic: group, tier, flag, draft, human-approve.
Only the *flagging* rules change by org type. A profile declares two thresholds and
the labels/output for them; the pipeline applies whichever the active profile sets.

- nonprofit: IRS written-acknowledgment rules (501(c)(3))
- campaign:  FEC contribution limit + itemization
- generic:   no regulatory layer (clubs, mutual aid, retail loyalty, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    # Cap that triggers refund-the-excess (thank for the capped amount only).
    # None = no cap (most orgs accept any amount).
    contribution_limit: float | None
    # Cumulative giving that triggers a compliance record. None = no reporting.
    report_threshold: float | None
    # Whether the threshold is inclusive: IRS is "$250 or more" (>=); FEC is
    # "in excess of $200" (strict >).
    report_inclusive: bool
    # Flag name on each donor row + the note describing what the record is for.
    report_flag: str
    report_filename: str
    report_note: str


PROFILES = {
    # 501(c)(3): a contemporaneous written acknowledgment is required for any
    # donor whose giving reaches $250 (IRS §170(f)(8)); it must state the amount
    # and whether goods/services were provided (quid pro quo). No giving cap.
    "nonprofit": Profile(
        name="nonprofit",
        contribution_limit=None,
        report_threshold=250.0,
        report_inclusive=True,
        report_flag="needs_acknowledgment",
        report_filename="data/acknowledgments.csv",
        report_note="IRS written acknowledgment (§170(f)(8)): state amount + no goods/services.",
    ),
    # Federal campaign: $3,500 per-person limit (refund the excess), itemize
    # donors over $200 for FEC filing.
    "campaign": Profile(
        name="campaign",
        contribution_limit=3500.0,
        report_threshold=200.0,
        report_inclusive=False,
        report_flag="needs_itemization",
        report_filename="data/donations_itemized.csv",
        report_note="FEC itemization (>$200 cycle total).",
    ),
    # No regulatory layer: tier + thank-you only.
    "generic": Profile(
        name="generic",
        contribution_limit=None,
        report_threshold=None,
        report_inclusive=False,
        report_flag="needs_report",
        report_filename="data/reportable.csv",
        report_note="",
    ),
}


def get_profile(name: str) -> Profile:
    if name not in PROFILES:
        raise ValueError(f"unknown profile {name!r}; choose from {sorted(PROFILES)}")
    return PROFILES[name]
