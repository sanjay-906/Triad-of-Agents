# waiter_agent.py
from __future__ import annotations

import logging
import os
import sys
import uuid

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from agent_base import (
    make_card, serve, emit_text, a2a_call,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


PORT = 9001
CHEF_URL = "http://localhost:9002"
INGREDIENTS_URL = "http://localhost:9003"
log = logging.getLogger("waiter_agent")

GOOGLE_MODEL = os.getenv("GOOGLE_MODEL")


async def ask_chef(order: str) -> str:
    """Forward a dish-preparation order to the Chef agent via A2A.

    Args:
        order: A clear instruction, e.g. "Prepare a margherita pizza".
    """
    text, _files = await a2a_call(CHEF_URL, order)
    # log.info(f"{os.getenv('GREEN')}Chef Agent: {text}{os.getenv('RESET')}")
    print(f"{Fore.YELLOW}Waiter Agent: {text}{Style.RESET_ALL}")
    return text or "(no answer from chef)"


async def ask_ingredients(dish_name: str) -> str:
    """Ask the Ingredients agent for the ingredient list of a dish via A2A.

    Args:
        dish_name: Name of the dish to look up, e.g. "margherita pizza".
    """
    text, _files = await a2a_call(INGREDIENTS_URL, dish_name)
    # log.info(f"{os.getenv('CYAN')}Ingredients Agent: {text}{os.getenv('RESET')}")
    print(f"{Fore.YELLOW}Waiter Agent: {text}{Style.RESET_ALL}")
    return text or "(no answer from ingredients_agent)"


adk_agent = LlmAgent(
    name="waiter_agent",
    model=GOOGLE_MODEL,
    instruction=(
        "You are the Waiter agent in a restaurant. You are the customer's "
        "single point of contact.\n"
        "• If the customer asks which ingredients a dish has, call "
        "`ask_ingredients(dish_name)`.\n"
        "• If the customer wants to actually prepare / cook a dish, first "
        "fetch its ingredients via `ask_ingredients`, then call "
        "`ask_chef(order)` with a clear instruction like "
        "'Prepare a <dish> with <ingredients>'.\n"
        "• Always reply in English, concisely, and present the chef's "
        "confirmation to the customer at the end.\n"
        "Examples:\n"
        "  Customer: 'What's in a margherita pizza?'\n"
        "    → call ask_ingredients('margherita pizza') and return the list.\n"
        "  Customer: 'Make me a spaghetti carbonara.'\n"
        "    → call ask_ingredients('spaghetti carbonara'), then call "
        "ask_chef('Prepare spaghetti carbonara with the ingredients listed').\n"
        "VERY IMPORTANT: There are many tables in our restaurant so return the table number from the chef agent"
    ),
    tools=[ask_chef, ask_ingredients],
)

_session_service = InMemorySessionService()
_runner = Runner(agent=adk_agent, app_name="restaurant", session_service=_session_service)


class WaiterExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        log.info("Waiter received: %s", user_text)

        try:
            session = await _session_service.create_session(
                app_name="restaurant",
                user_id="a2a_user",
                session_id=uuid.uuid4().hex,
            )
            content = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=user_text)],
            )
            answer_parts: list[str] = []
            async for event in _runner.run_async(
                user_id="a2a_user",
                session_id=session.id,
                new_message=content,
            ):
                if event.is_final_response() and event.content:
                    for p in event.content.parts:
                        if getattr(p, "text", None):
                            answer_parts.append(p.text)
            answer = "\n".join(answer_parts).strip() or "(no answer)"
        except Exception as exc:
            log.exception("waiter_agent error")
            answer = f"[waiter_agent] Internal error: {exc}"

        log.info("waiter_agent answer: %s", answer.replace("\n", " | ")[:300])
        await emit_text(event_queue, context, answer)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await emit_text(event_queue, context, "Cancellation not supported.")


SKILL = {
    "id": "restaurant_waiter",
    "name": "Restaurant waiter",
    "description": (
        "Front-of-house waiter. Tells customers which ingredients a dish has "
        "(delegates to the Ingredients_agent) and places cooking orders "
        "(delegates to the Chef agent)."
    ),
    "tags": ["waiter", "restaurant", "order", "menu"],
    "examples": [
        "What's in a margherita pizza?",
        "Make me a spaghetti carbonara",
        "Prepare a margherita pizza and tell me when it's ready",
    ],
}

CARD = make_card(
    name="waiter_agent",
    description="Google ADK waiter that orchestrates the Chef and Ingredients agents via A2A.",
    port=PORT,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[SKILL],
)


def main() -> None:
    serve(CARD, WaiterExecutor(), PORT, "waiter_agent")


if __name__ == "__main__":
    main()
