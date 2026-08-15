from __future__ import annotations

import logging
import sys
import os

from fastmcp import Client

from crewai import Agent, Crew, Task, LLM
from crewai.tools import tool as crew_tool

from agent_base import make_card, serve, emit_text

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue

from dotenv import load_dotenv

load_dotenv()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 9002
MCP_URL = "http://localhost:1906/mcp"

log = logging.getLogger("Chef Agent")


async def call_mcp_prepare_dish(
    name: str,
    ingredients: list[str],
) -> str:
    """Call the stateless Chef MCP service."""

    async with Client(MCP_URL) as client:
        result = await client.call_tool(
            "prepare_dish",
            {
                "name": name,
                "ingredients": ingredients,
            },
        )

        if not result.content:
            return "(no response from kitchen)"

        parts: list[str] = []

        for content in result.content:
            text = getattr(content, "text", None)

            if text is not None:
                parts.append(text)
            else:
                parts.append(str(content))

        return "\n".join(parts)


@crew_tool("prepare_dish_tool")
async def prepare_dish_tool(name: str, ingredients: list[str]) -> str:
    """Prepares a given dish provided the ingredients list."""

    return await call_mcp_prepare_dish(name=name, ingredients=ingredients)


_crew_llm = LLM(
    model=f"gemini/{os.getenv('GOOGLE_MODEL')}",

)

_chef_agent = Agent(
    role="Chef",
    goal=(
        "Prepare the dishes requested by the waiter "
        "and return confirmation."
    ),
    backstory=(
        "You are a skilled chef in a busy restaurant. "
        "You receive an order, inspect the requested dish name "
        "and ingredients, and prepare it by calling the "
        "prepare_dish tool. You always reply in English."
    ),
    tools=[prepare_dish_tool],
    llm=_crew_llm,
    verbose=False,
)


_crew = Crew(
    agents=[_chef_agent],
    tasks=[
        Task(
            description=(
                "Order to fulfil:\n{order}\n\n"
                "Use the prepare_dish tool to cook it. "
                "Then return the kitchen's confirmation "
                "to the waiter in plain English."
            ),
            expected_output=(
                "Confirmation that the dish is ready."
            ),
            agent=_chef_agent,
        )
    ],
    verbose=False,
)


class ChefExecutor(AgentExecutor):

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_text = context.get_user_input()

        log.info("Chef received order: %s", user_text)

        try:
            # No MCP connection is opened here.
            #
            # The MCP connection is opened only when CrewAI actually
            # invokes prepare_dish_tool().
            result = await _crew.kickoff_async(
                inputs={
                    "order": user_text,
                }
            )

            answer = str(result).strip()

            if not answer:
                answer = "(no answer from chef)"

        except Exception as exc:
            log.exception("Chef error")
            answer = f"[Chef Agent] Internal error: {exc}"

        log.info("Chef answer: %s", answer.replace("\n", " | ")[:300])

        await emit_text(event_queue, context, answer)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await emit_text(event_queue, context, "Cancellation not supported.")


SKILL = {
    "id": "dish_preparation",
    "name": "Dish preparation",
    "description": (
        "Prepares a dish given its name and ingredient list."
    ),
    "tags": [
        "chef",
        "cook",
        "kitchen",
        "prepare",
    ],
    "examples": [
        "Prepare a margherita pizza",
        "Cook spaghetti carbonara with eggs, bacon, parmesan, pepper",
    ],
}


CARD = make_card(
    name="Chef Agent",
    description=(
        "CrewAI agent that prepares dishes "
        "via the stateless chef MCP service."
    ),
    port=PORT,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[SKILL],
)


def main() -> None:
    serve(CARD, ChefExecutor(), PORT, "Chef Agent")


if __name__ == "__main__":
    main()
