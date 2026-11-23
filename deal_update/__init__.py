"""Scheduled deal-update writeback: propose, then the rep approves, edits or declines in Slack.

Nothing in this package writes to HubSpot. `executor.dry_run_write` records the exact payload that
would be sent and stops. Production writes need the FIN change ticket and a deliberate code change.
"""
