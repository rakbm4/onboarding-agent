# Edit Day Message Template

Interactively edit a specific day's onboarding message template in `agent.py`.

## Usage

```
/edit-template <day>
```

- `<day>` — day number to edit: 1, 2, 3, 4, or 5

## Steps

1. Read the current template for the specified day from `DAY_TEMPLATES` in `agent.py`
2. Display it clearly so the user can see the current content
3. Ask the user what they want to change — options:
   - Edit the greeting or intro paragraph
   - Add, remove, or reorder bullet points
   - Change the "Today's focus" section
   - Change the "What you should complete today" section
   - Change the footer/contact line
   - Replace the entire template
4. Apply the requested change using the Edit tool on `agent.py`
5. Show the final updated template so the user can confirm it looks right

## Important Rules
- The `<@SLACK_ID>` placeholder in the greeting MUST be preserved — it is replaced at runtime with the joiner's Slack mention. Never remove it.
- Each `👉 Open here` placeholder is replaced in order with real document links from the Google Sheet. The number of `👉 Open here` placeholders must match the number of documents configured for that day in Tab 3. Warn the user if they change this count.
- Do not modify any other part of `agent.py` — only the string value of the relevant key in `DAY_TEMPLATES`
