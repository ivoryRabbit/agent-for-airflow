"""Handles DE replies in alert threads and executes the requested action."""

from slack_sdk.web.async_client import AsyncWebClient

from app.agent import AirflowAgent
from app.store import thread_store

_agent = AirflowAgent()


async def _fetch_thread_history(client: AsyncWebClient, channel: str, thread_ts: str) -> list[dict]:
    """Return all messages in a thread as [{role, content}] for LLM context."""
    response = await client.conversations_replies(channel=channel, ts=thread_ts)
    messages = response.get("messages", [])
    history = []
    for msg in messages:
        role = "assistant" if msg.get("bot_id") else "user"
        content = msg.get("text", "")
        if content:
            history.append({"role": role, "content": content})
    return history


async def handle_reply(
    text: str,
    channel: str,
    thread_ts: str,
    message_ts: str,
    client: AsyncWebClient,
) -> None:
    """Interpret the DE's instruction and execute the appropriate Airflow action."""

    ctx = thread_store.get(thread_ts)
    thread_history = await _fetch_thread_history(client, channel, thread_ts)

    await client.reactions_add(channel=channel, name="thinking_face", timestamp=message_ts)

    try:
        if ctx is not None:
            # Known alert thread — treat as a DE instruction
            result = await _agent.handle_instruction(
                instruction=text,
                dag_id=ctx["dag_id"],
                dag_run_id=ctx["dag_run_id"],
                failed_tasks=ctx["failed_tasks"],
                thread_history=thread_history,
            )
        else:
            # General thread (e.g. after an @mention) — treat as a question
            result = await _agent.handle_general_question(text, thread_history=thread_history)
    except Exception as e:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f":warning: 오류가 발생했어요: {e}",
        )
        return

    await client.reactions_remove(channel=channel, name="thinking_face", timestamp=message_ts)
    await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=result)
