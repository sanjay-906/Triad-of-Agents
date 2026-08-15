from __future__ import annotations

import logging
import sys
import os

from dotenv import load_dotenv
from fastmcp import Client

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel

from agent_base import make_card, serve, emit_text

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

log = logging.getLogger("ingredients_agent")

PORT = 9003
MCP_URL = "http://localhost:1905/mcp"


async def call_mcp_get_ingredients(dish_name: str) -> str:
    """Call the stateless ingredients MCP server."""

    async with Client(MCP_URL) as client:
        result = await client.call_tool(
            "get_ingredients",
            {"name": dish_name},
        )

        if result.content:
            parts: list[str] = []

            for content in result.content:
                text = getattr(content, "text", None)

                if text is not None:
                    parts.append(text)
                else:
                    parts.append(str(content))

            return "\n".join(parts)

        return "(no ingredients returned)"


_model = GoogleModel(os.getenv("GOOGLE_MODEL"))


pydantic_agent = Agent(
    model=_model,
    system_prompt=(
        "You are the ingredients agent. "
        "Given a dish name, use the `get_ingredients` tool to fetch "
        "the ingredient list from the MCP service. "
        "Return the ingredients to the caller in plain English. "
        "If the dish is unknown, say so."
    ),
)


@pydantic_agent.tool
async def get_ingredients(ctx, dish_name: str) -> str:
    """Return all ingredients for the given dish name."""
    return await call_mcp_get_ingredients(dish_name)


class IngredientsExecutor(AgentExecutor):

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()

        log.info("Ingredients request: %s", user_text)

        try:
            result = await pydantic_agent.run(user_text)

            answer = result.output if isinstance(result.output, str) else str(result.output)
            answer = answer.strip() or "(no answer)"

        except Exception as exc:
            log.exception("ingredients_agent error")
            answer = f"[ingredients_agent] Internal error: {exc}"

        log.info("ingredients_agent answer: %s", answer.replace("\n", " | ")[:300])

        await emit_text(event_queue, context, answer)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await emit_text(event_queue, context, "Cancellation not supported.")


SKILL = {
    "id": "ingredients_lookup",
    "name": "Dish ingredients lookup",
    "description": "Returns the ingredient list for a given dish name.",
    "tags": [
        "ingredients",
        "recipe",
        "lookup",
    ],
    "examples": [
        "What are the ingredients of margherita pizza?",
        "List ingredients for spaghetti carbonara",
    ],
}


CARD = make_card(
    name="ingredients_agent",
    description=(
        "Pydantic AI agent that lists dish ingredients "
        "via the stateless ingredients MCP service."
    ),
    port=PORT,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[SKILL],
)


def main() -> None:
    serve(CARD, IngredientsExecutor(), PORT, "ingredients_agent")


if __name__ == "__main__":
    main()
