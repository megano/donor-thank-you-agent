"""Donor dedupe / tier / flag pipeline.

Step 1: read donations.csv, sum gifts per donor into donors_summed.csv (1 row/donor)
Step 2: assign tier (grassroots <$50, mid $50-100, major >$100)
Step 3: apply the active compliance profile's flags, and write the profile's
        compliance list (e.g. IRS acknowledgments, or FEC itemization).

The core (group, then tier) is gift-agnostic. The regulatory layer is pluggable:
set PROFILE to "nonprofit", "campaign", or "generic" (see compliance.py).
"""
import csv
import os
from collections import OrderedDict

from compliance import get_profile

PROFILE = get_profile(os.environ.get("DONOR_PROFILE", "nonprofit"))

def donor_key(row):
    # Group by email; fall back to name when email is missing (Marcus Hill).
    email = row["email"].strip().lower()
    if email:
        return ("email", email)
    return ("name", f"{row['first_name'].strip().lower()} {row['last_name'].strip().lower()}")

def tier_for(total):
    if total < 50:
        return "grassroots"
    if total <= 100:
        return "mid"
    return "major"

def main():
    summed = OrderedDict()
    with open("data/donations.csv") as f:
        for row in csv.DictReader(f):
            k = donor_key(row)
            amt = float(row["amount"])
            if k not in summed:
                summed[k] = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": row["email"].strip(),
                    "employer": row["employer"],
                    "occupation": row["occupation"],
                    "total": 0.0,
                    "gift_count": 0,
                }
            summed[k]["total"] += amt
            summed[k]["gift_count"] += 1

    limit = PROFILE.contribution_limit
    threshold = PROFILE.report_threshold
    flag = PROFILE.report_flag

    def reportable_amount(total):
        if threshold is None:
            return False
        return total >= threshold if PROFILE.report_inclusive else total > threshold

    rows = []
    for d in summed.values():
        total = round(d["total"], 2)
        over_limit = limit is not None and total > limit
        excess = round(total - limit, 2) if over_limit else 0.0
        # Thank-you amount: cap at the legal max for over-limit donors (campaigns);
        # otherwise thank for the full cumulative gift.
        thank_amount = limit if over_limit else total
        rows.append({
            **d,
            "total": total,
            "tier": tier_for(total),
            flag: reportable_amount(total),
            "over_limit": over_limit,
            "excess": excess,
            "thank_amount": thank_amount,
            "missing_email": d["email"] == "",
        })

    # donors_summed.csv
    fields = ["first_name", "last_name", "email", "employer", "occupation",
              "total", "gift_count", "tier", flag,
              "over_limit", "excess", "thank_amount", "missing_email"]
    with open("data/donors_summed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # compliance list (profile-specific: IRS acknowledgments, FEC itemization, ...)
    reportable = [r for r in rows if r[flag]] if threshold is not None else []
    if threshold is not None:
        with open(PROFILE.report_filename, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["first_name", "last_name", "employer", "occupation", "total"])
            for r in reportable:
                w.writerow([r["first_name"], r["last_name"], r["employer"],
                            r["occupation"], r["total"]])

    # console summary
    print(f"profile: {PROFILE.name}")
    print(f"donors: {len(rows)} (from raw rows)")
    for t in ("grassroots", "mid", "major"):
        n = sum(1 for r in rows if r["tier"] == t)
        print(f"  {t}: {n}")
    if threshold is not None:
        op = ">=" if PROFILE.report_inclusive else ">"
        print(f"{flag} ({op} ${threshold:.0f}): {len(reportable)} written to {PROFILE.report_filename}")
        if PROFILE.report_note:
            print(f"  {PROFILE.report_note}")
    over = [r for r in rows if r["over_limit"]]
    for r in over:
        print(f"  OVER LIMIT: {r['first_name']} {r['last_name']} "
              f"gave ${r['total']:.0f}, refund ${r['excess']:.0f}, thank for ${r['thank_amount']:.0f}")
    miss = [r for r in rows if r["missing_email"]]
    for r in miss:
        print(f"  MISSING EMAIL: {r['first_name']} {r['last_name']} (can't email, total ${r['total']:.0f})")

if __name__ == "__main__":
    main()
