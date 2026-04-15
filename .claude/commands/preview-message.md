# Preview Onboarding Message

Preview exactly what message will be sent to a joiner for a given day — without sending anything.

## Usage

```
/preview-message <day> [slack_id]
```

- `<day>` — onboarding day number: 1, 2, 3, 4, or 5 (required)
- `[slack_id]` — Slack user ID to substitute into the message (optional, defaults to `UPREVIEW`)

## Steps

1. Read `DAY_TEMPLATES[day]` from `agent.py`
2. Read `load_documents()` logic — fetch the Google Sheet Documents tab (Tab 3) live using the `GOOGLE_SHEET_ID` and `DOCS_SHEET_GID` from `.env`
3. Substitute `<@SLACK_ID>` with `<@{slack_id}>` (or `<@UPREVIEW>` if none given)
4. Replace each `👉 Open here` placeholder in order with the real document links fetched from the sheet
5. Display the final rendered message in a code block so the user can see exactly what the joiner will receive
6. Also show a table of which document links were used for that day

## Notes
- This is a read-only preview — no Slack API calls are made
- If the Documents sheet has no links for that day, placeholders will show as `👉 (link pending)`
