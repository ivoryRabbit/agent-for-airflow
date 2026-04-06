"""Slack Bolt app — entry point for the Airflow AI agent."""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from slack.agent import AirflowAgent
from slack.handlers.alert import handle_alert
from slack.handlers.reply import handle_reply
from slack.parser import is_failure_alert, parse_alert

_agent = AirflowAgent()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

ALERT_CHANNEL = os.environ["SLACK_ALERT_CHANNEL"]
AIRFLOW_BOT_USER = os.environ.get("SLACK_AIRFLOW_BOT_USER")
BOT_USER_ID: str | None = None  # resolved on startup


@app.event("message")
async def on_message(event: dict, client, say) -> None:
    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts")
    ts = event.get("ts")

    logger.info("message event | channel=%s user=%s thread_ts=%s text=%r", channel, user, thread_ts, text[:80])

    # @멘션 메시지는 app_mention 핸들러가 처리
    if BOT_USER_ID and f"<@{BOT_USER_ID}>" in text:
        return

    # ------------------------------------------------------------------ #
    # Top-level message in the alert channel → check if it's an alert     #
    # ------------------------------------------------------------------ #
    if channel == ALERT_CHANNEL and thread_ts is None:
        # Accept alerts from any user/bot, or restrict to AIRFLOW_BOT_USER if set.
        # Do NOT filter out BOT_USER_ID here — the DAG callback uses the same token.
        if AIRFLOW_BOT_USER and user != AIRFLOW_BOT_USER:
            logger.info("skipped: not from AIRFLOW_BOT_USER (%s)", AIRFLOW_BOT_USER)
            return

        if not is_failure_alert(text):
            logger.info("skipped: not a failure alert")
            return

        alert = parse_alert(text)
        if alert is None:
            logger.warning("Could not parse alert from message: %s", text)
            await client.chat_postMessage(
                channel=channel,
                thread_ts=ts,
                text=(
                    ":warning: I detected a failure alert but could not parse the DAG info.\n"
                    "Please share the `dag_id` and `dag_run_id` so I can investigate."
                ),
            )
            return

        asyncio.create_task(handle_alert(alert, channel, ts, client))

    # ------------------------------------------------------------------ #
    # Thread reply → treat as a DE instruction                            #
    # ------------------------------------------------------------------ #
    elif thread_ts is not None and channel == ALERT_CHANNEL:
        # Ignore the bot's own replies to avoid loops
        if user == BOT_USER_ID:
            return
        asyncio.create_task(handle_reply(text, channel, thread_ts, ts, client))


@app.event("app_mention")
async def on_mention(event: dict, client) -> None:
    import re
    channel = event.get("channel")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts") or ts
    text = re.sub(r"<@\w+>", "", event.get("text", "")).strip()

    if not text:
        return

    await client.reactions_add(channel=channel, name="thinking_face", timestamp=ts)

    try:
        response = await _agent.handle_general_question(text)
    except Exception as e:
        response = f":warning: 오류가 발생했어요: {e}"

    await client.reactions_remove(channel=channel, name="thinking_face", timestamp=ts)
    await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=response)


async def main() -> None:
    global BOT_USER_ID
    # Resolve the bot's own user ID to avoid self-replies
    auth = await app.client.auth_test()
    BOT_USER_ID = auth["user_id"]
    logger.info("Bot user ID: %s", BOT_USER_ID)

    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
