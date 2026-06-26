"""Donor thank-you agent.

Reads donors_summed.csv, and for one donor per tier asks Claude to write a
tone-matched thank-you in the organization's voice, then calls the
deliver_thank_you tool. By default that stages a Gmail draft for human review;
set DELIVERY_MODE=send to send, or DELIVERY_MODE=print to preview without Gmail.
Where a profile caps gifts (e.g. campaigns), over-limit donors are thanked for
the capped amount, not the full gift.

The voice is config-driven (ORG below) so the same agent serves any donor-funded
organization: nonprofit, club, mutual aid, campaign, etc.

Run: ANTHROPIC_API_KEY=... python agent.py            # draft mode (default)
     ANTHROPIC_API_KEY=... DELIVERY_MODE=print python agent.py
"""
import csv
import json
import os

import anthropic

import gmail_client

MODEL = "claude-opus-4-8"
SEND_TO = os.environ.get("SEND_TO", "drafts@example.org")  # override per run; default is a placeholder

# draft (default): create a Gmail draft for human review; send: send directly;
# print: no Gmail, just echo to the terminal (preview without OAuth setup).
DELIVERY_MODE = os.environ.get("DELIVERY_MODE", "draft")

# Edit this block to point the agent at a different organization.
ORG = {
    "name": "Example Community Fund",
    "signer_name": "Carmen Sandiego",
    "signer_title": "Executive Director",
    "mission": "a nonprofit funding food security and housing support",
}

VOICE = f"""You write thank-you notes on behalf of the {ORG['name']}, {ORG['mission']}.
Warm, plain-spoken, no jargon, no fundraising-blast tone.
One or two sentences of real thanks, then end with exactly these three lines and
nothing after them:
With gratitude,
{ORG['signer_name']}
{ORG['signer_title']}, {ORG['name']}
Tone by tier: grassroots = grateful for steady everyday support; mid = warm and
personal; major = warmer, more weight, acknowledge the size of the commitment.
When a donor is flagged over-limit, thank them for the capped amount, never the full gift."""

TOOLS = [{
    "name": "deliver_thank_you",
    "description": "Deliver a donor thank-you email. By default this stages a Gmail "
                   "draft for human review; the operator may configure it to send.",
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "recipient email"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
}]


def pick_one_per_tier(path="data/donors_summed.csv"):
    seen, picks = set(), []
    for r in csv.DictReader(open(path)):
        if r["missing_email"] == "True":
            continue  # can't email; handled by the flag report, not here
        if r["tier"] not in seen:
            seen.add(r["tier"])
            picks.append(r)
    return picks


def deliver_thank_you(to, subject, body):
    # Routes to a Gmail draft (default), a direct send, or a terminal preview,
    # per DELIVERY_MODE. See gmail_client.deliver.
    result = gmail_client.deliver(to, subject, body, DELIVERY_MODE)
    print(f"[{result['status'].upper()}] to={to} | subject={subject}")
    return result


def run_for_donor(client, donor):
    thank_amount = float(donor["thank_amount"])
    prompt = (
        f"Donor: {donor['first_name']} {donor['last_name']}, tier={donor['tier']}, "
        f"gave a cycle total to thank them for of ${thank_amount:.0f} "
        f"({donor['gift_count']} gift(s)). Over-limit: {donor['over_limit']}. "
        f"Write the thank-you and call deliver_thank_you with to={SEND_TO}."
    )
    messages = [{"role": "user", "content": prompt}]
    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=VOICE,
            thinking={"type": "adaptive"},
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use" and block.name == "deliver_thank_you":
                out = deliver_thank_you(**block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out),
                })
        messages.append({"role": "user", "content": results})


def main():
    if DELIVERY_MODE not in ("draft", "send", "print"):
        raise SystemExit(f"DELIVERY_MODE must be draft, send, or print (got {DELIVERY_MODE!r})")
    print(f"delivery mode: {DELIVERY_MODE}")
    client = anthropic.Anthropic()
    for donor in pick_one_per_tier():
        run_for_donor(client, donor)


if __name__ == "__main__":
    main()
