# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Agent

```bash
# Activate the venv first
venv/Scripts/activate      # Windows PowerShell: venv\Scripts\Activate.ps1

# Run the agent
python agent.py
```

All secrets are read from `.env` (local) or GitHub Secrets (CI). Required vars: `SLACK_BOT_TOKEN`, `SLACK_LOG_CHANNEL`, `GOOGLE_SHEET_ID`. Optional: `JOINERS_SHEET_GID` (default `0`), `HOLIDAYS_SHEET_GID` (default `713153074`), `DOCS_SHEET_GID`.

## Architecture

Everything lives in `agent.py`. No Anthropic/Claude API is used — messages are composed from hardcoded templates. The flow on each run:

1. **Load holidays** from Google Sheet Tab 2 → skip if today is a weekend or holiday
2. **Load joiners** from Google Sheet Tab 1 → for each, call `get_onboarding_day()` to determine if today is Day 1–5 of their onboarding
3. **Load documents** from Google Sheet Tab 3 → keyed by day number (1–5)
4. **For each active joiner**: call `send_dm_for_joiner()` — resolves Slack user ID, opens DM channel, fills the day template via `compose_message()`, and posts via `slack_post()`
5. **Post summary** via `post_summary()` — calls `slack_post()` directly to the log channel

## Key Design Decisions

**Hardcoded day templates**: `DAY_TEMPLATES` (dict, keys 1–5) holds the full message text for each onboarding day. `compose_message()` fills them by replacing `<@SLACK_ID>` with the joiner's Slack mention and substituting each `👉 Open here` placeholder in order with real document links from the sheet.

**Google Sheets as the data store**: All three data sources (joiners, holidays, documents) are fetched live as CSV exports from a public Google Sheet. Column headers are normalised to lowercase with spaces/underscores stripped, so `"Joining Date"`, `"joining_date"`, and `"joiningdate"` all resolve to the same key.

**Scheduling logic**: `get_onboarding_day()` only accepts Monday (weekday 0) or Wednesday (weekday 2) as valid joining dates. It walks forward day-by-day counting working days, so company holidays automatically push remaining onboarding days forward with no config changes.

**Slack user resolution**: `resolve_user_id()` accepts either a U-prefixed user ID directly or falls back to `users.lookupByEmail` using the joiner's email. `open_dm_channel()` then calls `conversations.open` to get the DM channel ID before posting.

**No AI/LLM involvement**: Messages are composed entirely from templates in code. There is no Anthropic SDK, no `ANTHROPIC_API_KEY`, and no Claude API call.

## Google Sheet Structure

| Tab | GID | Required columns |
|-----|-----|-----------------|
| Joiners | `0` | Name, Email, SlackID (or SlackUserID), Joining Date |
| Holidays | `713153074` | Date (YYYY-MM-DD or YYYY/MM/DD), Holiday Name |
| Documents | (set via `DOCS_SHEET_GID`) | Day (1–5), Document Name (or DocName), Link (or URL) |

Dates in the sheet may use either `/` or `-` as separators — both are handled.

## GitHub Actions

The workflow at `.github/workflows/onboarding_agent.yml` runs this agent on a schedule. All environment variables are injected as GitHub Secrets with the same names as `.env`.
