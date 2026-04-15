# Dry Run — Simulate Today's Agent Run

Simulate exactly what the agent would do today without sending any Slack messages.

## Steps

1. Load `.env` variables
2. Determine today's date
3. Fetch holidays from Tab 2 — check if today is a working day. If not, report "Agent would skip today" and stop.
4. Fetch joiners from Tab 1
5. Fetch documents from Tab 3
6. For each joiner:
   - Parse their joining date
   - Call `get_onboarding_day()` logic to determine if today is Day 1–5 for them
   - If yes: show which day it is and display the fully rendered message (with real doc links substituted) that WOULD be sent
   - If no: show "no message today" with a brief reason (e.g. "not in onboarding window", "bad date format", "not Mon/Wed joiner")
7. Show what the summary message to the log channel would look like

## Output Format

```
=== DRY RUN — 2026-04-15 ===

✅ Working day — agent would run

Joiners processed: 33

📨 Alice Smith — Day 2
  Channel: DM
  Message preview:
  ─────────────────
  Hi <@U123ABC>,
  Happy Day 2 of your onboarding!
  ...
  ─────────────────

⏭  Bob Jones — no message today (not in onboarding window)
❌  Carol Lee — bad date format: '15-04-2026' (must be YYYY-MM-DD)

=== SUMMARY (would post to #log-channel) ===
✅ Alice Smith — Day 2
```

## Notes
- No Slack API calls are made (no `chat.postMessage`, no `conversations.open`)
- Google Sheets ARE fetched live — this validates the sheet is accessible
- Useful to run before a new batch of joiners starts to confirm everything looks right
