"""Smoke test: pipeline runs and produces the expected shape under each profile."""
import csv
import os

import pipeline
from compliance import get_profile


def run(profile_name):
    os.environ["DONOR_PROFILE"] = profile_name
    # pipeline binds PROFILE at import; rebind for the test.
    pipeline.PROFILE = get_profile(profile_name)
    pipeline.main()
    return list(csv.DictReader(open("data/donors_summed.csv")))


def test_nonprofit():
    summed = run("nonprofit")
    assert len(summed) == 17, f"expected 17 donors, got {len(summed)}"

    # No contribution cap for a nonprofit: nobody is over-limit.
    assert not any(r["over_limit"] == "True" for r in summed)

    # IRS acknowledgment needed at $250 or more (inclusive).
    acks = list(csv.DictReader(open("data/acknowledgments.csv")))
    assert len(acks) == 6, f"expected 6 acknowledgments, got {len(acks)}"
    # James Park gave exactly $250, so the inclusive threshold catches him.
    assert any(r["last_name"] == "Park" for r in acks)

    # aggregation handled: Maria's two gifts ($25 + $200 = $225) stay under $250.
    maria = next(r for r in summed if r["last_name"] == "Alvarez")
    assert maria["needs_acknowledgment"] == "False"

    missing = [r for r in summed if r["missing_email"] == "True"]
    assert len(missing) == 1 and missing[0]["last_name"] == "Hill"
    print("nonprofit smoke test passed")


def test_campaign():
    summed = run("campaign")
    assert len(summed) == 17

    itemized = list(csv.DictReader(open("data/donations_itemized.csv")))
    assert len(itemized) == 7, f"expected 7 itemized, got {len(itemized)}"

    over = [r for r in summed if r["over_limit"] == "True"]
    assert len(over) == 1 and over[0]["last_name"] == "Suzuki"
    assert float(over[0]["excess"]) == 1500.0
    assert float(over[0]["thank_amount"]) == 3500.0

    # aggregation trap: Maria's two gifts ($25 + $200) cross $200 only when summed
    maria = next(r for r in summed if r["last_name"] == "Alvarez")
    assert maria["needs_itemization"] == "True"
    print("campaign smoke test passed")


if __name__ == "__main__":
    test_nonprofit()
    test_campaign()
