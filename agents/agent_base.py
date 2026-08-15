# agent_base.py
from __future__ import annotations

import logging
import uuid

# for _s in (sys.stdout, sys.stderr):
#     try:
#         _s.reconfigure(encoding="utf-8")
#     except Exception:
#         pass


import httpx
import uvicorn
from google.protobuf import json_format
from starlette.applications import Starlette
from a2a.types import a2a_pb2 as pb
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory

from dotenv import load_dotenv

load_dotenv()


AGENT_CARD_PATH = "/.well-known/agent-card.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def text_part(s: str) -> pb.Part:
    return pb.Part(text=s)


def file_part(data: bytes, name: str, media_type: str) -> pb.Part:
    return pb.Part(raw=data, filename=name, media_type=media_type)


def proto_to_py(obj):
    if hasattr(obj, "keys"):
        return {k: proto_to_py(obj[k]) for k in obj.keys()}
    if isinstance(obj, (str, bytes, int, float, bool)) or obj is None:
        return obj
    try:
        return [proto_to_py(x) for x in obj]
    except TypeError:
        return obj


def request_metadata(context: RequestContext) -> dict:
    try:
        return proto_to_py(context.metadata or {})
    except Exception:
        return {}


def make_card(
    *,
    name: str,
    description: str,
    port: int,
    default_input_modes: list[str],
    default_output_modes: list[str],
    skills: list[dict],
) -> pb.AgentCard:
    return json_format.ParseDict(
        {
            "name": name,
            "description": description,
            "version": "1.0.0",
            "supported_interfaces": [
                {
                    "url": f"http://localhost:{port}",
                    "protocol_binding": "JSONRPC",
                    "protocol_version": "1.0",
                }
            ],
            "capabilities": {"streaming": False, "push_notifications": False},
            "default_input_modes": default_input_modes,
            "default_output_modes": default_output_modes,
            "skills": skills,
        },
        pb.AgentCard(),
    )


def serve(card: pb.AgentCard, executor: AgentExecutor, port: int, label: str) -> None:
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = create_agent_card_routes(card) + create_jsonrpc_routes(handler, "/")
    app = Starlette(routes=routes)
    logging.getLogger(label).info(
        "Starting '%s' on http://localhost:%s (card: %s)",
        label, port, AGENT_CARD_PATH,
    )
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


async def emit_text(event_queue: EventQueue, context: RequestContext, text: str) -> None:
    await event_queue.enqueue_event(
        pb.Task(
            id=context.task_id,
            context_id=context.context_id,
            status=pb.TaskStatus(state=pb.TASK_STATE_SUBMITTED),
        )
    )
    u = TaskUpdater(event_queue, context.task_id, context.context_id)
    await u.start_work()
    await u.complete(u.new_agent_message([text_part(text)]))


async def emit_text_and_file(
    event_queue: EventQueue,
    context: RequestContext,
    text: str,
    data: bytes,
    fname: str,
    media_type: str,
) -> None:
    await event_queue.enqueue_event(
        pb.Task(
            id=context.task_id,
            context_id=context.context_id,
            status=pb.TaskStatus(state=pb.TASK_STATE_SUBMITTED),
        )
    )
    u = TaskUpdater(event_queue, context.task_id, context.context_id)
    await u.start_work()
    await u.add_artifact([file_part(data, fname, media_type)], name=fname)
    await u.complete(u.new_agent_message([text_part(text)]))


async def a2a_call(
    base_url: str,
    message: str,
    metadata: dict | None = None,
    timeout: float = 120.0,
) -> tuple[str, list[tuple[str, bytes, str]]]:
    """Connect to another agent via A2A, send a text message, return its text + files."""
    async with httpx.AsyncClient(timeout=timeout) as hc:
        card = await A2ACardResolver(
            hc, base_url, agent_card_path=AGENT_CARD_PATH
        ).get_agent_card()
        client = ClientFactory(
            ClientConfig(httpx_client=hc, streaming=False)
        ).create(card)
        msg = pb.Message(
            message_id=uuid.uuid4().hex,
            role=pb.ROLE_USER,
            parts=[text_part(message)],
        )
        req = pb.SendMessageRequest(message=msg)
        if metadata:
            req.metadata.update(metadata)
        text_out = ""
        files: list[tuple[str, bytes, str]] = []
        async for ev in client.send_message(req):
            m = ev.message if ev.HasField("message") else None
            t = ev.task if ev.HasField("task") else None
            if m:
                text_out += "".join(p.text for p in m.parts if p.text)
            if t:
                if t.status and t.status.message:
                    text_out += "".join(
                        p.text for p in t.status.message.parts if p.text
                    )
                for a in t.artifacts:
                    for p in a.parts:
                        if p.raw:
                            files.append(
                                (a.name or p.filename or "file", p.raw, p.media_type)
                            )
        return text_out.strip(), files
