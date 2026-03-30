import asyncio
import os
import logging
import requests
import anthropic
from datetime import date, timedelta
from dotenv import load_dotenv

# Load .env for local development (ignored in GitHub Actions)
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config (from .env locally, from GitHub Secrets in production) ──────────────
SLACK_BOT_TOKEN    = os.environ["SLACK_BOT_TOKEN"]
SLACK_LOG_CHANNEL  = os.environ["SLACK_LOG_CHANNEL"]
GOOGLE_SHEET_ID    = os.environ["GOOGLE_SHEET_ID"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
JOINERS_SHEET_GID  = os.environ.get("JOINERS_SHEET_GID", "0")
HOLIDAYS_SHEET_GID = os.environ.get("HOLIDAYS_SHEET_GID", "713153074")
DOCS_SHEET_GID     = os.environ.get("DOCS_SHEET_GID", "")

# Populated at runtime from Google Sheet Documents tab
DAY_DOCS = {1: [], 2: [], 3: [], 4: [], 5: []}

DAY_THEMES = {
    1: "Welcome Day 🎉 — first impressions and settling in",
    2: "Getting Oriented 🗺️ — tools, people, and processes",
    3: "Diving Deeper 🚀 — getting hands-on with the role",
    4: "Building Connections 🤝 — culture and teammates",
    5: "First Week Done 🏆 — reflection and what comes next",
}


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


# ── Anthropic API — Claude composes and sends the DM ──────────────────────────
SEND_DM_TOOL = {
    "name": "send_slack_dm",
    "description": "Send an onboarding Slack DM directly to a new joiner.",
    "input_schema": {
        "type": "object",
        "properties": {
            "slack_id": {"type": "string", "description": "The joiner's Slack Member ID or email."},
            "message":  {"type": "string", "description": "The fully composed Slack-formatted message."},
        },
        "required": ["slack_id", "message"],
    },
}


async def run_agent_for_joiner(name: str, slack_id: str, email: str, day: int, docs: list):
    """
    Resolves the DM channel, then calls the Anthropic API. Claude composes the
    onboarding DM via the send_slack_dm tool call, which we dispatch to Slack.
    """
    user_id = resolve_user_id(slack_id, email)
    if not user_id:
        logger.error(f"    ❌ Could not resolve Slack user for {name} (id={slack_id}, email={email})")
        return False

    dm_channel = open_dm_channel(user_id)
    if not dm_channel:
        logger.error(f"    ❌ Could not open DM channel for {name} ({user_id})")
        return False

    doc_text = "\n".join(
        f"• {title}: {link if link else '[link pending]'}"
        for title, link in docs
    )

    prompt = (
        f"Send a Day {day} onboarding Slack DM to a new joiner.\n\n"
        f"Joiner name: {name}\n"
        f"Slack ID: {dm_channel}\n"
        f"Day: {day} of 5\n"
        f"Theme: {DAY_THEMES[day]}\n"
        f"Documents to share:\n{doc_text}\n\n"
        f"Steps:\n"
        f"1. Think about where {name} is in their journey — Day {day} of 5\n"
        f"2. Compose a warm, concise, motivating Slack DM with Slack markdown\n"
        f"3. Weave all document links naturally into the message\n"
        f"4. Call send_slack_dm with the slack_id and the final message"
    )

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You are an autonomous HR onboarding AI agent. "
            "Your job is to craft warm, personalised onboarding Slack DMs "
            "for new joiners and send them using the send_slack_dm tool. "
            "Always use Slack markdown (*bold*, _italic_, • bullets). "
            "Never use placeholder text like [Manager Name]."
        ),
        tools=[SEND_DM_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "send_slack_dm":
            dm_message = block.input["message"]
            ok = slack_post(dm_channel, dm_message)
            if ok:
                logger.info(f"    ✅ DM sent to {name} ({user_id})")
            else:
                logger.error(f"    ❌ Failed to send DM to {name} ({user_id})")
            return ok

    logger.warning(f"    ⚠️  Claude did not call send_slack_dm for {name}")
    return False


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
async def main():
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

        logger.info(f"  🤖 Running agent for {j['name']} — Day {day_num}")

        try:
            await run_agent_for_joiner(
                name=j["name"],
                slack_id=j["slack_id"],
                email=j["email"],
                day=day_num,
                docs=DAY_DOCS[day_num]
            )
            sent.append(f"✅ {j['name']} — Day {day_num}")
        except Exception as e:
            logger.error(f"  ❌ Error for {j['name']}: {e}")
            failed.append(f"❌ {j['name']} — Day {day_num} ({str(e)})")

    logger.info("📊 Posting daily summary to Slack log channel...")
    post_summary(sent, failed, today)
    logger.info("🏁 Agent run complete.")


if __name__ == "__main__":
    asyncio.run(main())
