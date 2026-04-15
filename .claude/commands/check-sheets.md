# Check Google Sheets Data

Fetch and display current data from all 3 Google Sheet tabs used by the agent.

## Steps

Read `GOOGLE_SHEET_ID` and all GID vars from `.env`, then:

### Tab 1 — Joiners
- Fetch CSV from GID `JOINERS_SHEET_GID` (default: `0`)
- Display as a table: Name | Email | SlackID | Joining Date
- Flag any rows with:
  - Missing Name or Joining Date
  - Joining Date not on a Monday or Wednesday
  - Joining Date in bad format (not YYYY-MM-DD or YYYY/MM/DD)
  - Missing both SlackID and Email (can't resolve user)

### Tab 2 — Holidays
- Fetch CSV from GID `HOLIDAYS_SHEET_GID` (default: `713153074`)
- Display as a table: Date | Holiday Name
- Flag any dates not in YYYY-MM-DD or YYYY/MM/DD format

### Tab 3 — Documents
- Fetch CSV from GID `DOCS_SHEET_GID`
- Display as a table grouped by Day: Day | Document Name | Link
- Flag any rows where Day is not 1–5 or Link is empty

### Summary
- Total joiners, holidays, documents per day
- Count of validation warnings found
- Whether today is a working day (not weekend/holiday)

## Notes
- This is read-only — no writes are made to the sheet
- If a tab fails to load, show the HTTP error and how to fix it (usually sheet not public)
