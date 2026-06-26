"""Gmail delivery for the donor thank-you agent.

Delivery mode (set DELIVERY_MODE):
  draft (default): create a Gmail draft for human review. Nothing sends until a
    person opens it and hits send. This is the on-ramp: read what the agent wrote,
    confirm it's accurate, build trust.
  send: send the email directly. Switch to this once you trust the drafts.
  print: no Gmail at all; echo to the terminal. Lets you preview the agent without
    setting up OAuth.

Draft is the default on purpose: a new user should see and vet the emails before
the agent is allowed to send anything on their behalf.

Auth (draft/send only): OAuth desktop flow. Create an OAuth client ID (type
"Desktop app") in Google Cloud Console, under APIs & Services then Credentials,
download it to credentials.json. First run opens a browser to authorize; the token
is then cached in token.json. Both files are gitignored; never commit them.
"""
import base64
import os
from email.message import EmailMessage

# gmail.compose is the least-privilege scope that covers both creating drafts and
# sending. It cannot read the inbox.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def _service():
    # Imported lazily so `print` mode works without the Google libraries installed.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"{CREDENTIALS_FILE} not found. Download an OAuth desktop client "
                    "from Google Cloud Console and save it here, or run with "
                    "DELIVERY_MODE=print to preview without Gmail."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _raw(to, subject, body):
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def deliver(to, subject, body, mode="draft"):
    """Create a draft (default), send, or print. Returns a short status dict."""
    if mode == "print":
        print(f"[PREVIEW] to={to} | subject={subject}\n{body}\n")
        return {"status": "printed", "to": to}

    service = _service()
    raw = _raw(to, subject, body)
    if mode == "draft":
        d = service.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}).execute()
        return {"status": "drafted", "to": to, "draft_id": d["id"]}
    if mode == "send":
        m = service.users().messages().send(
            userId="me", body={"raw": raw}).execute()
        return {"status": "sent", "to": to, "message_id": m["id"]}
    raise ValueError(f"unknown DELIVERY_MODE {mode!r}; use draft, send, or print")
