# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Agent

```bash
# Activate the venv first
venv/Scripts/activate      # Windows PowerShell: venv\Scripts\Activate.ps1

# Run the agent
python agent.py
```

All secrets are read from `.env` (local) or GitHub Secrets (CI). Required vars: `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_LOG_CHANNEL`, `GOOGLE_SHEET_ID`. Optional: `JOINERS_SHEET_GID` (default `0`), `HOLIDAYS_SHEET_GID` (default `713153074`), `DOCS_SHEET_GID`.

## Architecture

Everything lives in `agent.py`. The flow on each run:

1. **Load holidays** from Google Sheet Tab 2 → skip if today is a weekend or holiday
2. **Load joiners** from Google Sheet Tab 1 → for each, call `get_onboarding_day()` to determine if today is Day 1–5 of their onboarding
3. **Load documents** from Google Sheet Tab 3 → keyed by day number (1–5)
4. **For each active joiner**: call `run_agent_for_joiner()` — hits the Anthropic API with a `send_slack_dm` tool; Claude composes the message and the tool call is intercepted to dispatch via `slack_post()`
5. **Post summary** via `post_summary()` — calls `slack_post()` directly (no Claude involved)

## Key Design Decisions

**Google Sheets as the data store**: All three data sources (joiners, holidays, documents) are fetched live as CSV exports from a public Google Sheet. Column headers are normalised to lowercase with spaces/underscores stripped, so `"Joining Date"`, `"joining_date"`, and `"joiningdate"` all resolve to the same key.

**Scheduling logic**: `get_onboarding_day()` only accepts Monday (weekday 0) or Wednesday (weekday 2) as valid joining dates. It walks forward day-by-day counting working days, so company holidays automatically push remaining onboarding days forward with no config changes.

**Claude via Anthropic SDK, not `claude_agent_sdk`**: The bundled `claude.exe` in `claude-agent-sdk` uses Claude Code subscription credits, not `ANTHROPIC_API_KEY`. Use `anthropic.AsyncAnthropic` directly. The model is hardcoded to `claude-sonnet-4-6`.

**Tool-forced message composition**: `tool_choice={"type": "any"}` forces Claude to always call `send_slack_dm` rather than responding with text. The tool call is never actually sent to Slack by Claude — `agent.py` intercepts `block.type == "tool_use"` and calls `slack_post()` itself.

## Google Sheet Structure

| Tab | GID | Required columns |
|-----|-----|-----------------|
| Joiners | `0` | Name, Email, SlackID (or SlackUserID), Joining Date |
| Holidays | `713153074` | Date (YYYY-MM-DD or YYYY/MM/DD), Holiday Name |
| Documents | `1162985988` | Day (1–5), Document Name (or DocName), Link (or URL) |

Dates in the sheet may use either `/` or `-` as separators — both are handled.

## GitHub Actions

The workflow at `.github/workflows/onboarding_agent.yml` runs this agent on a schedule. All environment variables are injected as GitHub Secrets with the same names as `.env`.
