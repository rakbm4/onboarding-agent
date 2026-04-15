# Check Agent Configuration

Verify all required environment variables and configuration are correct before running the agent.

## Steps

1. Read the `.env` file (if it exists)
2. Check for each required variable and report status:

   | Variable | Required | Expected format |
   |---|---|---|
   | `SLACK_BOT_TOKEN` | Yes | starts with `xoxb-` |
   | `SLACK_LOG_CHANNEL` | Yes | starts with `C` (channel ID) |
   | `GOOGLE_SHEET_ID` | Yes | 44-char alphanumeric string |
   | `JOINERS_SHEET_GID` | No (default: `0`) | numeric string |
   | `HOLIDAYS_SHEET_GID` | No (default: `713153074`) | numeric string |
   | `DOCS_SHEET_GID` | No | numeric string |

3. For each missing or malformed variable, show what it should look like and where to get it
4. Verify the Google Sheet is publicly accessible by attempting to fetch a small CSV from Tab 1 (GID 0)
5. Test the Slack token by calling `https://slack.com/api/auth.test` with the token and reporting the bot name and workspace
6. Print a final PASS/FAIL summary

## Notes
- Never print the full token value — show only first 10 chars + `...`
- The `.env` file is gitignored; it should never be committed
