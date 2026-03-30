import asyncio
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
SLACK_BOT_TOKEN    = os.environ["SLACK_BOT_TOKEN"]
SLACK_LOG_CHANNEL  = os.environ["SLACK_LOG_CHANNEL"]
GOOGLE_SHEET_ID    = os.environ["GOOGLE_SHEET_ID"]
JOINERS_SHEET_GID  = os.environ.get("JOINERS_SHEET_GID", "0")
HOLIDAYS_SHEET_GID = os.environ.get("HOLIDAYS_SHEET_GID", "713153074")
DOCS_SHEET_GID     = os.environ.get("DOCS_SHEET_GID", "")

DAY_DOCS = {1: [], 2: [], 3: [], 4: [], 5: []}

# ── Day message templates (no API needed) ──────────────────────────────────────
DAY_TEMPLATES = {
    1: """\
👋 *Welcome to the team, {name}!* 🎉

We're so excited to have you here on your very first day! Today is all about settling in, getting comfortable, and knowing that you're warmly welcomed by everyone.

*Here's what to focus on today:*
• Get set up on all your tools and systems
• Familiarise yourself with the office/remote setup
• Don't hesitate to ask questions — there are no silly ones!

{docs}

You've got this! Wishing you an amazing first day. 🚀""",

    2: """\
Good morning, *{name}!* 🗺️

Day 2 — you're already finding your feet! Today is about getting oriented: understanding our tools, meeting the right people, and learning how we work.

*Today's focus:*
• Explore the tools and platforms we use daily
• Connect with your immediate team members
• Review key processes relevant to your role

{docs}

You're doing great — keep the curiosity going! 💡""",

    3: """\
Hey *{name}!* 🚀

Halfway through your first week — and it's time to dive deeper! Today is about getting hands-on and starting to feel the rhythm of your role.

*Today's focus:*
• Start engaging with your first real tasks or projects
• Ask your manager or buddy for a deeper walkthrough of priorities
• Take notes on things you want to revisit later

{docs}

You're making great progress — the team can already feel your energy! ⚡""",

    4: """\
Hi *{name}!* 🤝

Day 4 — it's all about building connections today. The work is important, but so are the people you work with!

*Today's focus:*
• Reach out to a colleague you haven't spoken to yet
• Learn about how different teams collaborate
• Share something about yourself in the team channel — people love to know you!

{docs}

The best ideas come from great relationships. You're building something special here! 🌟""",

    5: """\
*Congratulations, {name}!* 🏆

You've made it to the end of your first week — and what a week it's been! Take a moment to reflect on how far you've come in just five days.

*To close out the week:*
• Jot down your wins, questions, and goals for Week 2
• Share feedback with your manager about the onboarding experience
• Celebrate — you officially belong here! 🎊

{docs}

The whole team is rooting for you. Here's to many more great weeks ahead! 🥂""",
}


def build_doc_section(docs: list) -> str:
    """Format document links into a Slack-friendly bullet list."""
    if not docs:
        return ""
    lines = ["", "*📎 Resources for today:*"]
    for title, link in docs:
        if link:
            lines.append(f"• <{link}|{title}>")
        else:
            lines.append(f"• {title}")
    return "\n".join(lines)


def compose_message(name: str, day: int, docs: list) -> str:
    """Fill the day template with the joiner's name and their documents."""
    doc_section = build_doc_section(docs)
    return DAY_TEMPLATES[day].format(name=name, docs=doc_section).strip()


# ── Google Sheet helpers ───────────────────────────────────────────────────────
def fetch_sheet_tab(sheet_id: str, gid: str) -> list:
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
    rows = fetch_sheet_tab(GOOGLE_SHEET_ID, JOINERS_SHEET_GID)
    joiners = []
    for r in rows:
        name    = r.get("name", "").strip()
        email   = r.get("email", "").strip()
        slack   = (r.get("slackid", "") or r.get("slackuserid", "")).strip()
        joining = (r.get("joiningdate", "") or r.get("joindate", "")).strip()
        if name and joining:
            joiners.append({"name": name, "email": email, "slack_id": slack, "joining": joining})
    logger.info(f"Loaded {len(joiners)} joiners from sheet.")
    return joiners


def load_company_holidays() -> set:
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
    try:
        rows = fetch_sheet_tab(GOOGLE_SHEET_ID, DOCS_SHEET_GID)
        docs = {1: [], 2: [], 3: [], 4: [], 5: []}
        for r in rows:
            day  = r.get("day", "").strip()
            name = (r.get("documentname", "") or r.get("docname", "") or r.get("name", "")).strip()
            link = (r.get("link", "") or r.get("url", "") or r.get("documentlink", "")).strip()
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
    return d.weekday() < 5 and d.isoformat() not in holidays


def get_onboarding_day(joining: date, today: date, holidays: set):
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
    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
        json={"channel": channel, "text": text},
        timeout=10,
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


def send_onboarding_dm(name: str, slack_id: str, email: str, day: int, docs: list) -> bool:
    user_id = resolve_user_id(slack_id, email)
    if not user_id:
        logger.error(f"    ❌ Could not resolve Slack user for {name} (id={slack_id}, email={email})")
        return False

    dm_channel = open_dm_channel(user_id)
    if not dm_channel:
        logger.error(f"    ❌ Could not open DM channel for {name} ({user_id})")
        return False

    message = compose_message(name, day, docs)
    ok = slack_post(dm_channel, message)
    if ok:
        logger.info(f"    ✅ DM sent to {name} ({user_id}) — Day {day}")
    else:
        logger.error(f"    ❌ Failed to send DM to {name} ({user_id})")
    return ok


def post_summary(sent: list, failed: list, today: date):
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
        ok = send_onboarding_dm(
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
