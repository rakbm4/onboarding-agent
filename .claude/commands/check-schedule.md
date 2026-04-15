# Check Onboarding Schedule

Given a joining date, show the full 5-day onboarding schedule with exact calendar dates.

## Usage

```
/check-schedule <joining-date>
```

- `<joining-date>` — format: YYYY-MM-DD (must be a Monday or Wednesday)

## Steps

1. Parse the joining date
2. Validate it is a Monday (weekday 0) or Wednesday (weekday 2) — if not, explain the constraint and suggest the nearest valid date
3. Load company holidays from the Google Sheet (Tab 2, same logic as `load_company_holidays()` in `agent.py`)
4. Walk forward from the joining date using `get_onboarding_day()` logic, counting only working days (Mon–Fri, excluding holidays)
5. Produce a table:

   | Day | Date | Weekday | Notes |
   |-----|------|---------|-------|
   | 1   | YYYY-MM-DD | Monday | Joining day |
   | 2   | YYYY-MM-DD | Tuesday | |
   | 3   | YYYY-MM-DD | Wednesday | |
   | 4   | YYYY-MM-DD | Thursday | |
   | 5   | YYYY-MM-DD | Friday | |

   If a holiday falls in the week, show it as a skipped row and push remaining days forward.

6. Also show which of these days have already passed, which is today, and which are upcoming

## Notes
- Holidays are fetched live from the sheet — result reflects the latest holiday list
- All 5 onboarding days are working days; weekends and holidays are automatically skipped
