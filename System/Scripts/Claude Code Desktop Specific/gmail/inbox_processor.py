#!/Users/ericmanchester/theVault/.venv/bin/python3
"""
inbox_processor.py
-------------------
Interactive inbox-zero tool. Fetches batches of messages from a specified
Gmail mailbox, prints summaries, and accepts bulk decisions.

Designed to be run by Claude who presents batches to the user for decisions,
then executes them via the Gmail API.

Usage:
    python inbox_processor.py --account exchange --batch 20
    python inbox_processor.py --account google   --batch 20
    python inbox_processor.py --query "in:inbox is:unread" --batch 20

Decisions per batch (applied to all or selectively):
    archive   → remove INBOX label, add Archive/YYYY label
    delete    → move to trash
    import    → add _VAULT_IMPORT label (email_to_vault.py picks it up)
    keep      → leave in inbox as-is
    label:X   → add custom label X
"""

import sys
import re
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from gmail_auth import get_service


# ── ACCOUNT → INBOX QUERY MAP ─────────────────────────────────────────────────
ACCOUNT_QUERIES = {
    "exchange": "in:inbox",          # primary inbox across all accounts
    "google":   "in:inbox",
    "icloud":   "in:inbox",
    "all":      "in:inbox",
}


def get_headers(msg):
    return {h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])}


def format_message(msg, index):
    h = get_headers(msg)
    ts  = int(msg.get("internalDate", 0)) / 1000
    dt  = datetime.fromtimestamp(ts, tz=timezone.utc)
    age = (datetime.now(tz=timezone.utc) - dt).days

    subj   = h.get("Subject", "(no subject)")[:70]
    sender = h.get("From", "")[:50]
    labels = [l for l in msg.get("labelIds", [])
              if l not in ("INBOX", "UNREAD", "IMPORTANT")]

    age_str = f"{age}d ago" if age > 0 else "today"
    unread  = "●" if "UNREAD" in msg.get("labelIds", []) else " "
    label_str = f" [{', '.join(labels[:3])}]" if labels else ""

    return (f"  [{index:>3}] {unread} {age_str:>8}  "
            f"{sender:<35}  {subj}{label_str}")


def fetch_batch(svc, query, max_results, page_token=None):
    params = {"userId": "me", "q": query, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    result = svc.users().messages().list(**params).execute()
    msgs = result.get("messages", [])
    next_token = result.get("nextPageToken")

    full = []
    for m in msgs:
        full_msg = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date", "To"]
        ).execute()
        full.append(full_msg)
    return full, next_token


def get_or_create_label(svc, name, _cache={}):
    if name in _cache:
        return _cache[name]
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    for lbl in labels:
        if lbl["name"] == name:
            _cache[name] = lbl["id"]
            return lbl["id"]
    body = {"name": name, "labelListVisibility": "labelShow",
            "messageListVisibility": "show"}
    lbl_id = svc.users().labels().create(userId="me", body=body).execute()["id"]
    _cache[name] = lbl_id
    return lbl_id


def archive_year(dt):
    return f"Archive/{dt.year}"


def apply_decision(svc, msgs, decision):
    """Apply a decision string to a list of messages."""
    ids = [m["id"] for m in msgs]

    if decision == "archive":
        # Group by year for proper archive label
        by_year = defaultdict(list)
        for m in msgs:
            ts = int(m.get("internalDate", 0)) / 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            by_year[dt.year].append(m["id"])

        for year, year_ids in by_year.items():
            lbl_id = get_or_create_label(svc, f"Archive/{year}")
            for i in range(0, len(year_ids), 100):
                svc.users().messages().batchModify(
                    userId="me",
                    body={"ids": year_ids[i:i+100],
                          "addLabelIds": [lbl_id],
                          "removeLabelIds": ["INBOX"]}
                ).execute()
                time.sleep(0.3)
        print(f"    ✓ Archived {len(ids)} messages")

    elif decision == "delete":
        for i in range(0, len(ids), 100):
            svc.users().messages().batchModify(
                userId="me",
                body={"ids": ids[i:i+100], "addLabelIds": ["TRASH"],
                      "removeLabelIds": ["INBOX"]}
            ).execute()
            time.sleep(0.3)
        print(f"    ✓ Trashed {len(ids)} messages")

    elif decision == "import":
        import_id = get_or_create_label(svc, "_VAULT_IMPORT")
        for i in range(0, len(ids), 100):
            svc.users().messages().batchModify(
                userId="me",
                body={"ids": ids[i:i+100], "addLabelIds": [import_id]}
            ).execute()
            time.sleep(0.3)
        print(f"    ✓ Labeled {len(ids)} messages _VAULT_IMPORT")

    elif decision == "keep":
        print(f"    ✓ Kept {len(ids)} messages in inbox")

    elif decision.startswith("label:"):
        label_name = decision.split(":", 1)[1].strip()
        lbl_id = get_or_create_label(svc, label_name)
        for i in range(0, len(ids), 100):
            svc.users().messages().batchModify(
                userId="me",
                body={"ids": ids[i:i+100], "addLabelIds": [lbl_id]}
            ).execute()
            time.sleep(0.3)
        print(f"    ✓ Applied label '{label_name}' to {len(ids)} messages")

    else:
        print(f"    ⚠ Unknown decision: {decision}")


def group_by_sender(msgs):
    """Group messages by sender domain for easier bulk decisions."""
    groups = defaultdict(list)
    for m in msgs:
        h = get_headers(m)
        sender = h.get("From", "")
        match = re.search(r'@([\w.]+)', sender)
        domain = match.group(1) if match else "unknown"
        groups[domain].append(m)
    return dict(sorted(groups.items(), key=lambda x: -len(x[1])))


def print_grouped(groups):
    print("\n── Grouped by sender domain ──────────────────────────────")
    for i, (domain, msgs) in enumerate(groups.items()):
        sample_subj = get_headers(msgs[0]).get("Subject", "")[:50]
        print(f"  [{i:>2}] {len(msgs):>4}x  {domain:<35} e.g. \"{sample_subj}\"")


def run(query, batch_size, grouped=True):
    svc = get_service()

    # Count total
    count_result = svc.users().messages().list(
        userId="me", q=query, maxResults=1
    ).execute()
    est = count_result.get("resultSizeEstimate", "?")
    print(f"\n══ Inbox Processor ══════════════════════════")
    print(f"  Query:  {query}")
    print(f"  ~{est} messages matching")
    print(f"  Batch:  {batch_size}")
    print(f"══════════════════════════════════════════════\n")

    page_token = None
    total_processed = 0

    while True:
        msgs, page_token = fetch_batch(svc, query, batch_size, page_token)
        if not msgs:
            print("✓ No more messages.")
            break

        print(f"\n── Batch ({len(msgs)} messages) ──────────────────────────")

        if grouped:
            groups = group_by_sender(msgs)
            print_grouped(groups)
            print("\nOptions per group number:")
            print("  archive / delete / import / keep / label:X")
            print("  'all archive' = apply to entire batch at once")
            print("  'flat' = show individual message list instead")
            print("  'skip' = move to next batch")
            print("  'quit' = stop\n")

            cmd = input("Decision (group# action  OR  all action  OR  flat): ").strip().lower()

            if cmd == "quit":
                break
            elif cmd == "skip":
                total_processed += len(msgs)
                continue
            elif cmd == "flat":
                for i, m in enumerate(msgs):
                    print(format_message(m, i))
                cmd = input("\nDecision (index# or range# action, or 'all action'): ").strip().lower()

            if cmd.startswith("all "):
                decision = cmd[4:].strip()
                apply_decision(svc, msgs, decision)
                total_processed += len(msgs)

            elif re.match(r'^\d+\s+\w', cmd):
                parts = cmd.split(None, 1)
                group_idx = int(parts[0])
                decision  = parts[1]
                domain_keys = list(groups.keys())
                if group_idx < len(domain_keys):
                    domain   = domain_keys[group_idx]
                    selected = groups[domain]
                    apply_decision(svc, selected, decision)
                    total_processed += len(selected)
                else:
                    print("  Invalid group index")

            else:
                print("  Skipping (unrecognized command)")

        else:
            for i, m in enumerate(msgs):
                print(format_message(m, i))
            print("\nDecisions: archive / delete / import / keep / label:X")
            print("  'all archive' = entire batch | 'quit' = stop\n")
            cmd = input("Decision: ").strip().lower()

            if cmd == "quit":
                break
            elif cmd.startswith("all "):
                apply_decision(svc, msgs, cmd[4:].strip())
                total_processed += len(msgs)

        print(f"\n  Running total processed: {total_processed}")

        if not page_token:
            print("\n✓ All batches complete.")
            break

        cont = input("\nNext batch? (y/n): ").strip().lower()
        if cont != "y":
            break

    print(f"\n══ Done. Total processed: {total_processed} ══")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query",   default="in:inbox", help="Gmail search query")
    parser.add_argument("--batch",   type=int, default=20, help="Messages per batch")
    parser.add_argument("--flat",    action="store_true", help="List view instead of grouped")
    args = parser.parse_args()

    run(query=args.query, batch_size=args.batch, grouped=not args.flat)
