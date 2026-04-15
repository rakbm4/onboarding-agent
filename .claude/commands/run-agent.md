# Run Onboarding Agent

Execute the onboarding agent locally and report results clearly.

## Steps

1. Activate the Python venv: `venv/Scripts/activate`
2. Run: `python agent.py`
3. Capture full stdout/stderr output
4. Parse the log lines and produce a clean summary:
   - How many joiners were loaded
   - Which joiners received a DM and on which day (✅ lines)
   - Which joiners failed (❌ lines)
   - Whether the Slack summary was posted successfully
   - Whether the agent skipped today (weekend/holiday)
5. If any errors appear, highlight them and suggest the likely fix

## Error Quick-Reference

| Log pattern | Likely cause | Fix |
|---|---|---|
| `KeyError: 'SLACK_BOT_TOKEN'` | Missing `.env` var | Add `SLACK_BOT_TOKEN` to `.env` |
| `Could not resolve Slack user` | Bad SlackID or email in sheet | Check Tab 1 SlackID/email column |
| `Slack error ... not_in_channel` | Bot not in log channel | Invite bot to the channel |
| `HTTP 403` on Google Sheet | Sheet not public | Share sheet → Anyone with link → Viewer |
| `Bad date format` | Date not YYYY-MM-DD or YYYY/MM/DD | Fix date in Tab 1 |
