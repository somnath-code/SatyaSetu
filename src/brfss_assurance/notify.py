"""Send only ticket routing metadata to an explicitly configured Logic App."""

import json
import os
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def dispatch(tickets, send=False):
    url = os.environ.get("LOGIC_APP_CALLBACK_URL", "")
    if send and (urlsplit(url).scheme != "https" or not urlsplit(url).hostname):
        raise ValueError("Set LOGIC_APP_CALLBACK_URL to the HTTPS request trigger URL")
    results = []
    opener = build_opener(NoRedirect())
    for ticket in tickets.list():
        if ticket["status"] != "OPEN" or ticket["notification"] != "PENDING":
            continue
        payload = {k: ticket[k] for k in ("id", "request_id", "version", "role", "code")}
        if not send:
            results.append({"mode": "DRY_RUN", **payload})
            continue
        if not tickets.claim_notification(ticket["id"]):
            continue
        delivered = False
        try:
            request = Request(url, data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(request, timeout=30) as response:
                delivered = response.status == 200
        except OSError:
            # A timeout may happen after email delivery. Reconcile before any resend.
            pass
        tickets.finish_notification(ticket["id"], delivered)
        results.append({"mode": "SENT" if delivered else "CHECK_DELIVERY", **payload})
    return results
