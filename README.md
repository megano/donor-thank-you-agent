# Donor Thank-You Agent

Reads a donor export, deduplicates by donor, aggregates multi-gift donors, assigns
giving tiers, applies a pluggable compliance profile, and drafts tone-matched
thank-you emails in the organization's voice. A human approves before anything sends.

Works for any donor-funded organization: nonprofit, club, mutual aid, campaign. The
regulatory layer is a config profile, not baked into the core.

Sample data is synthetic (no real donors; addresses use reserved example domains).

## Run

Requires Python 3.11+. The pipeline step has no third-party deps; the agent step
needs Anthropic plus the Google client libraries:

```bash
pip install -r requirements.txt
```

```bash
python pipeline.py            # defaults to the nonprofit profile
DONOR_PROFILE=campaign python pipeline.py
DONOR_PROFILE=generic python pipeline.py
```

Outputs:
- `data/donors_summed.csv`: one row per donor, with tier and compliance flags
- a profile-specific compliance list (e.g. `data/acknowledgments.csv` for nonprofits,
  `data/donations_itemized.csv` for campaigns)

## What it does

1. **Dedupe + aggregate**: groups gifts by donor (email, name fallback). A donor who
   gave three times is summed, so threshold tests use the cumulative amount, not a
   single gift.
2. **Tier**: grassroots (<$50), mid ($50 to $100), major (>$100).
3. **Flag** (per the active profile):
   - *reportable*: cumulative giving crosses the profile's threshold
   - *over limit* (campaigns only): giving exceeds the legal cap; refund the excess,
     thank for the capped amount
   - *missing contact*: no email; flagged, not dropped

`agent.py` is the LLM tool-use loop: it reads each tier's donor and drafts a
tone-matched thank-you in the org's voice (the `ORG` block re-skins it), then calls a
`deliver_thank_you` tool. Run it with `ANTHROPIC_API_KEY` set.

## Email delivery

`deliver_thank_you` routes through the real Gmail API (`gmail_client.py`). The mode
is set with `DELIVERY_MODE`:

| Mode | Behavior |
|---|---|
| `draft` (default) | Creates a Gmail **draft** for human review. Nothing sends until a person opens it. |
| `send` | Sends the email directly. |
| `print` | No Gmail; echoes the email to the terminal. Lets you try the agent without OAuth setup. |

Draft is the default by design: see and vet what the agent writes before letting it
send on your behalf. Switch to `send` once you trust the drafts.

```bash
ANTHROPIC_API_KEY=... python agent.py                     # draft (default)
ANTHROPIC_API_KEY=... DELIVERY_MODE=print python agent.py # preview, no Gmail
ANTHROPIC_API_KEY=... DELIVERY_MODE=send  python agent.py # send for real
```

**Gmail setup (for `draft`/`send`):** create an OAuth client ID of type *Desktop app*
in Google Cloud Console (APIs & Services, then Credentials), download it to
`credentials.json` in the repo root. First run opens a browser to authorize and caches
the token in `token.json`. The scope is `gmail.compose` (create/send only, no inbox
read). **`credentials.json` and `token.json` are gitignored; never commit them.**

## Compliance profiles

The core is gift-agnostic (group, tier, draft, human-approve). The compliance layer
is pluggable (`compliance.py`):

| Profile | Cap | Reporting trigger | Note |
|---|---|---|---|
| `nonprofit` | none | cumulative >= $250 | IRS written acknowledgment (170(f)(8)) |
| `campaign` | $3,500 (refund excess) | cumulative > $200 | FEC itemization |
| `generic` | none | none | tier + thank-you only |

Add an org type by adding a `Profile` entry, no change to the pipeline.

## Test

```bash
python test_smoke.py
```

Covers both the nonprofit and campaign profiles, including the aggregation case
(two sub-threshold gifts that only cross the line when summed) and the missing-contact
flag.
