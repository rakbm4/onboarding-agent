import os
import logging
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

# Load .env for local development (ignored in GitHub Actions)
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN    = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_LOG_CHANNEL  = os.environ.get("SLACK_LOG_CHANNEL", "")
GOOGLE_SHEET_ID    = os.environ.get("GOOGLE_SHEET_ID", "")
JOINERS_SHEET_GID  = os.environ.get("JOINERS_SHEET_GID", "0")
HOLIDAYS_SHEET_GID = os.environ.get("HOLIDAYS_SHEET_GID", "713153074")
DOCS_SHEET_GID     = os.environ.get("DOCS_SHEET_GID", "")

# Populated at runtime from Google Sheet Documents tab
DAY_DOCS = {1: [], 2: [], 3: [], 4: [], 5: []}

# ── Day message templates ──────────────────────────────────────────────────────
# <@SLACK_ID> is replaced at runtime with the joiner's actual Slack mention.
# Each "👉 Open here" is replaced in order with the real doc links from the sheet.

DAY_TEMPLATES = {
    1: """\
Hi <@SLACK_ID>,

Welcome to Day 1 of your onboarding at phData! 🎉
Today is about getting familiar with how we work and how we communicate.

*Today's focus:*
• Understand phData's general information, structure, and key references
• Learn our email and Slack/Teams etiquette so you can communicate confidently from day one

*Resources to review:*

General Information Folder
👉 Open here

Email and Slack Guidelines
👉 Open here

*What you should complete today:*
• Spend ~45–60 minutes going through both folders
• Note down:
  - Any questions on working hours, leave, basic processes
  - Any doubts on how to write messages, tone, tagging, and channels

If anything is unclear, you can email our People Ops team at india_hr@phdata.io and they'll be happy to help.""",

    2: """\
Hi <@SLACK_ID>,

Happy Day 2 of your onboarding!
Today is focused on understanding our employee policies, benefits, and how our People & IT teams operate globally.

*Today's focus:*
• Learn about employee policies, benefits, and your responsibilities
• Understand how to get HR and IT help when you need it

*Resources to review:*

Employee and Benefits Policies
👉 Open here

Global People and IT Operations
👉 Open here

*What you should complete today:*
• Spend ~60–90 minutes reviewing:
  - Leave and holiday policy
  - Benefits overview (health, reimbursements, etc., as applicable)
• Whom to contact for:
  - HR-related queries
  - Laptop / access / IT issues

*Suggested notes to capture:*
• HR contact details and escalation path
• IT support channels and working hours
• Any specific benefits you want to follow up on

If anything is unclear, you can email our People Ops team at india_hr@phdata.io and they'll be happy to help.""",

    3: """\
Hi <@SLACK_ID>,

Welcome to Day 3!
Today you'll get hands-on with GreytHR, our HR platform for attendance, leave, and payslips.

*Today's focus:*
• Understand how to log in to GreytHR
• Learn the basics you'll use regularly: attendance, leaves, payslips, and profile

*Resource to review:*

GreytHR Walkthrough
👉 Open here

*What you should complete today:*

Inside GreytHR (using the walkthrough as reference), please try to:
• Log in successfully
• Open your profile and verify your basic details
• Locate:
  - Attendance / time section
  - Leave section (how to apply / view balance)
  - Payslip section

If any option/page is missing or you can't log in, please let us know so we can help fix access.

If anything is unclear, you can email our People Ops team at india_hr@phdata.io and they'll be happy to help.""",

    4: """\
Hi <@SLACK_ID>,

You're on Day 4 of your onboarding.
Today is dedicated to POSH (Prevention of Sexual Harassment) – a mandatory and very important part of our culture and compliance.

*Today's focus:*
• Understand our POSH policy and zero-tolerance stance
• Learn how to raise concerns safely and confidentially
• Know your rights and responsibilities as an employee

*Resources to complete:*

POSH materials (policy / training content / assessment if present)
👉 Open here

*What you should complete today:*
• Go through:
  - POSH policy document
  - Any slides/videos included
  - Any quiz/acknowledgement (if provided in the folder)
• Make sure you understand:
  - What qualifies as harassment
  - Reporting channels and POCs
  - Confidentiality and non-retaliation guidelines

If anything is unclear, you can email our People Ops team at india_hr@phdata.io and they'll be happy to help.

If anything is sensitive or you're unsure about how to report a case, mention that you need a private clarification and we'll route it appropriately.""",

    5: """\
Hi <@SLACK_ID>,

Congrats on reaching Day 5 of your onboarding! 👏
Today we'll close the initial onboarding loop with the Employee Handbook acknowledgement.

*Today's focus:*
• Ensure you've read and understood the Employee Handbook
• Sign/submit the acknowledgement form as required

*Resource to complete:*

Acknowledgement Form of Employee Handbook
👉 Open here

*What you should complete today:*
• Open and review the Employee Handbook (if linked from or referenced in the form)
• Fill in all required details in the acknowledgement form
• Submit it as per the instructions given (e.g., upload to a folder / email to HR / submit via system)

If the submission instructions are unclear or you don't see where to upload/send it, please ping here so we can guide you.

If anything is unclear, you can email our People Ops team at india_hr@phdata.io and they'll be happy to help.""",
}


def compose_message(user_id: str, day: int, docs: list) -> str:
    """
    Fill the day template:
    - Replace <@SLACK_ID> with the joiner's actual Slack mention.
    - Replace each '👉 Open here' in order with the real doc link from the sheet.
    """
    message = DAY_TEMPLATES[day].replace("<@SLACK_ID>", f"<@{user_id}>")
    for _, link in docs:
        replacement = f"👉 {link}" if link else "👉 (link pending)"
        message = message.replace("👉 Open here", replacement, 1)
    return message


# ── Google Sheet helpers ───────────────────────────────────────────────────────
def fetch_sheet_tab(sheet_id: str, gid: str) -> list:
    """Fetch any tab from a public Google Sheet as CSV and return list of row dicts."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    lines = r.text.strip().split("\n")
    if len(lines) < 2:
        return []
    headers = [h.strip().lower().replace(" ", "").replace("_", "") for h in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        vals = [v.strip().strip('"') for v in line.split(",")]
        rows.append(dict(zip(headers, vals)))
    return rows


def load_joiners() -> list:
    """
    Load new joiners from Tab 1 of Google Sheet.
    Expected columns: Name, Email, SlackID, Joining Date
    """
    rows = fetch_sheet_tab(GOOGLE_SHEET_ID, JOINERS_SHEET_GID)
    joiners = []
    for r in rows:
        name    = r.get("name", "").strip()
        email   = r.get("email", "").strip()
        slack   = (r.get("slackid", "") or r.get("slackuserid", "")).strip()
        joining = (r.get("joiningdate", "") or r.get("joindate", "")).strip()
        if name and joining:
            joiners.append({
                "name": name,
                "email": email,
                "slack_id": slack,
                "joining": joining
            })
    logger.info(f"Loaded {len(joiners)} joiners from sheet.")
    return joiners


def load_company_holidays() -> set:
    """
    Load company holidays from Tab 2 of Google Sheet.
    Expected columns: Date (YYYY-MM-DD), Holiday Name
    Update this tab every year — agent reads it live, zero code changes needed.
    """
    try:
        rows = fetch_sheet_tab(GOOGLE_SHEET_ID, HOLIDAYS_SHEET_GID)
        holidays = set()
        for r in rows:
            d = (r.get("date", "") or r.get("holidaydate", "")).strip()
            if d:
                holidays.add(d)
        logger.info(f"Loaded {len(holidays)} company holidays from sheet.")
        return holidays
    except Exception as e:
        logger.warning(f"Could not load holidays: {e}. Proceeding with no holidays.")
        return set()


def load_documents() -> dict:
    """
    Load document links from Tab 3 of Google Sheet.
    Expected columns: Day, Document Name, Link
    """
    try:
        rows = fetch_sheet_tab(GOOGLE_SHEET_ID, DOCS_SHEET_GID)
        docs = {1: [], 2: [], 3: [], 4: [], 5: []}
        for r in rows:
            day  = r.get("day", "").strip()
            name = (
                r.get("documentname", "")
                or r.get("docname", "")
                or r.get("name", "")
            ).strip()
            link = (
                r.get("link", "")
                or r.get("url", "")
                or r.get("documentlink", "")
            ).strip()
            if day.isdigit() and name:
                d = int(day)
                if 1 <= d <= 5:
                    docs[d].append((name, link))
        logger.info(f"Loaded documents: { {k: len(v) for k, v in docs.items()} }")
        return docs
    except Exception as e:
        logger.warning(f"Could not load documents: {e}. Proceeding with no documents.")
        return {1: [], 2: [], 3: [], 4: [], 5: []}


# ── Working day & scheduling logic ────────────────────────────────────────────
def is_working_day(d: date, holidays: set) -> bool:
    """Returns True if the date is Monday–Friday and not a company holiday."""
    return d.weekday() < 5 and d.isoformat() not in holidays


def get_onboarding_day(joining: date, today: date, holidays: set):
    """
    Returns which onboarding day number (1–5) today is for a joiner, or None.

    Monday joiner:
      Day1=Mon · Day2=Tue · Day3=Wed · Day4=Thu · Day5=Fri (same week)

    Wednesday joiner:
      Day1=Wed · Day2=Thu · Day3=Fri · Day4=next Mon · Day5=next Tue

    If a company holiday falls in between, the remaining days shift
    forward by one working day automatically.
    """
    if joining.weekday() not in (0, 2):
        logger.warning(f"Joining date {joining} is not a Monday or Wednesday — skipping.")
        return None
    if not is_working_day(joining, holidays):
        logger.warning(f"Joining date {joining} falls on a company holiday — skipping.")
        return None
    current = joining
    day_num = 0
    while current <= today:
        if is_working_day(current, holidays):
            day_num += 1
            if current == today:
                return day_num if 1 <= day_num <= 5 else None
        current += timedelta(days=1)
    return None


# ── Slack helpers ──────────────────────────────────────────────────────────────
def slack_post(channel: str, text: str) -> bool:
    """Post a message to any Slack channel or DM."""
    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"channel": channel, "text": text},
        timeout=10
    )
    result = r.json()
    if not result.get("ok"):
        logger.error(f"Slack error for {channel}: {result.get('error')}")
    return result.get("ok", False)


def resolve_user_id(slack_id: str, email: str) -> str | None:
    """
    Resolve a reliable Slack user ID (U-prefix).
    1. If already a U-prefixed user ID, use it directly.
    2. Otherwise look up by email via users.lookupByEmail.
    """
    if slack_id.startswith("U"):
        return slack_id
    if email:
        r = requests.get(
            "https://slack.com/api/users.lookupByEmail",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            params={"email": email},
            timeout=10,
        )
        result = r.json()
        if result.get("ok"):
            uid = result["user"]["id"]
            logger.info(f"    Resolved {email} → {uid}")
            return uid
        logger.warning(f"    users.lookupByEmail failed for {email}: {result.get('error')}")
    return None


def open_dm_channel(user_id: str) -> str | None:
    """Open (or retrieve) a DM channel for a U-prefixed user ID."""
    r = requests.post(
        "https://slack.com/api/conversations.open",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
        json={"users": user_id},
        timeout=10,
    )
    result = r.json()
    if result.get("ok"):
        return result["channel"]["id"]
    logger.error(f"conversations.open failed for {user_id}: {result.get('error')}")
    return None


def send_dm_for_joiner(name: str, slack_id: str, email: str, day: int, docs: list) -> bool:
    """Resolve the DM channel, compose from template, and send."""
    user_id = resolve_user_id(slack_id, email)
    if not user_id:
        logger.error(f"    ❌ Could not resolve Slack user for {name} (id={slack_id}, email={email})")
        return False

    dm_channel = open_dm_channel(user_id)
    if not dm_channel:
        logger.error(f"    ❌ Could not open DM channel for {name} ({user_id})")
        return False

    message = compose_message(user_id, day, docs)
    ok = slack_post(dm_channel, message)
    if ok:
        logger.info(f"    ✅ DM sent to {name} ({user_id}) — Day {day}")
    else:
        logger.error(f"    ❌ Failed to send DM to {name} ({user_id})")
    return ok


def post_summary(sent: list, failed: list, today: date):
    """Post the daily onboarding summary directly to the Slack log channel."""
    lines = [f"*🤖 Onboarding Agent Summary — {today}*"]
    if sent:
        lines += ["", "*Messages Sent:*"] + sent
    if failed:
        lines += ["", "*Failed:*"] + failed
    if not sent and not failed:
        lines.append("_No onboarding messages scheduled for today._")
    ok = slack_post(SLACK_LOG_CHANNEL, "\n".join(lines))
    if ok:
        logger.info("Summary posted to Slack log channel.")
    else:
        logger.error("Failed to post summary to Slack log channel.")


# ── Main orchestrator ──────────────────────────────────────────────────────────
def main():
    for var in ("SLACK_BOT_TOKEN", "SLACK_LOG_CHANNEL", "GOOGLE_SHEET_ID"):
        if not os.environ.get(var):
            raise SystemExit(f"Missing required environment variable: {var}")
    today    = date.today()
    holidays = load_company_holidays()

    if not is_working_day(today, holidays):
        logger.info(f"⏸  Today ({today}) is a weekend or company holiday — agent skipping.")
        return

    logger.info(f"🤖 Onboarding Agent starting — {today}")

    joiners = load_joiners()
    DAY_DOCS.update(load_documents())

    sent, failed = [], []

    for j in joiners:
        try:
            joining_date = date.fromisoformat(j["joining"].replace("/", "-"))
        except ValueError:
            logger.warning(f"Bad date format for {j['name']}: '{j['joining']}' — must be YYYY-MM-DD or YYYY/MM/DD")
            continue

        day_num = get_onboarding_day(joining_date, today, holidays)

        if not day_num:
            logger.info(f"  ⏭  {j['name']} — no message today")
            continue

        logger.info(f"  📨 Sending Day {day_num} message to {j['name']}")

        ok = send_dm_for_joiner(
            name=j["name"],
            slack_id=j["slack_id"],
            email=j["email"],
            day=day_num,
            docs=DAY_DOCS[day_num],
        )
        if ok:
            sent.append(f"✅ {j['name']} — Day {day_num}")
        else:
            failed.append(f"❌ {j['name']} — Day {day_num}")

    logger.info("📊 Posting daily summary to Slack log channel...")
    post_summary(sent, failed, today)
    logger.info("🏁 Agent run complete.")


if __name__ == "__main__":
    main()
