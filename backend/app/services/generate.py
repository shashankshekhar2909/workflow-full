import json
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.schemas.workflow import GenerateRequest, WorkflowData
from app.services.openai_client import get_openai_client


def _extract_text(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text
    if hasattr(response, "choices") and response.choices:
        return response.choices[0].message.content
    if hasattr(response, "output") and response.output:
        for item in response.output:
            if getattr(item, "content", None):
                for content in item.content:
                    text = getattr(content, "text", None)
                    if text:
                        return text
    raise ValueError("Unable to extract text from OpenAI response")


def generate_workflow(payload: GenerateRequest) -> WorkflowData:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")

    client = get_openai_client()

    schema = WorkflowData.model_json_schema()

    system_prompt = (
        "Return ONLY a JSON object with keys: id, name, updatedAt, nodes, edges.\n"
        "Use valid node types only: start, webhook_trigger, schedule_trigger, task, http_request, transform_mapper, "
        "validator, delay, delay_wait, decision, switch_router, parallel_fork, join_merge, loop_foreach, manual_review, "
        "log_event, notify_alert, end, end_fail.\n"
        "Each node must be: { id, type, position: {x,y}, data: {label, description?, status, color?, ...} }.\n"
        "Each edge must be: { id, source, target, sourceHandle? }.\n"
        "Always include at least one start-type node and one end-type node."
    )

    mode = payload.mode
    user_prompt = (
        f"Description: {payload.description}\n"
        f"Mode: {mode}.\n"
        "Use status 'Ready' for node data status field.\n"
        "Provide ids like node_1, node_2 and edge_1, edge_2."
    )
    if payload.existing_workflow and mode == "append":
        user_prompt += (
            "\nExisting workflow JSON follows. Append new nodes to the right (offset x by +400). "
            "Preserve existing nodes/edges and connect the last reachable end to the new start when possible.\n"
            f"Existing: {payload.existing_workflow.model_dump()}"
        )

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = _extract_text(response)
    data = json.loads(raw)
    if "id" not in data:
        data["id"] = "wf_generated"
    if "name" not in data:
        data["name"] = payload.name or "Generated Workflow"
    if "updatedAt" not in data:
        data["updatedAt"] = datetime.utcnow().isoformat()
    nodes = data.get("nodes", [])
    for idx, node in enumerate(nodes, start=1):
        node.setdefault("id", f"node_{idx}")
        node.setdefault("position", {"x": (idx - 1) * 260, "y": 0})
        node.setdefault("data", {"label": node.get("type", "Node"), "status": "Ready"})
    edges = data.get("edges", [])
    for idx, edge in enumerate(edges, start=1):
        edge.setdefault("id", f"edge_{idx}")

    # Ensure at least one start-like trigger and one end node exist
    has_start = any(n.get("type") in ("start", "webhook_trigger", "schedule_trigger") for n in nodes)
    if not has_start:
        nodes.insert(
            0,
            {
                "id": "node_start",
                "type": "start",
                "position": {"x": 0, "y": 0},
                "data": {"label": "Start", "status": "Ready"},
            },
        )
        if nodes[1:]:
            edges.insert(0, {"id": "edge_start_1", "source": "node_start", "target": nodes[1]["id"]})

    has_end = any(n.get("type") in ("end", "end_fail") for n in nodes)
    if not has_end:
        last = nodes[-1] if nodes else {"id": "node_start"}
        end_id = "node_end"
        nodes.append(
            {
                "id": end_id,
                "type": "end",
                "position": {"x": (len(nodes)) * 260, "y": 0},
                "data": {"label": "End", "status": "Ready"},
            }
        )
        edges.append({"id": "edge_end_1", "source": last["id"], "target": end_id})

    # Ensure there is at least a simple path connecting nodes if edges are missing or disconnected
    if nodes:
        incoming = {node["id"]: 0 for node in nodes}
        for edge in edges:
            target = edge.get("target")
            if target in incoming:
                incoming[target] += 1

        edge_counter = len(edges)
        for idx in range(1, len(nodes)):
            node_id = nodes[idx]["id"]
            if incoming.get(node_id, 0) == 0:
                edge_counter += 1
                edges.append(
                    {
                        "id": f"edge_{edge_counter}",
                        "source": nodes[idx - 1]["id"],
                        "target": node_id,
                    }
                )
                incoming[node_id] = 1

    # Normalize positions to a tidy horizontal flow
    for idx, node in enumerate(nodes):
        node["position"] = {"x": idx * 260, "y": 0}

    data["nodes"] = nodes
    data["edges"] = edges
    return WorkflowData.model_validate(data)
