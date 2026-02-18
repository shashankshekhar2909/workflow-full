from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


NodeType = Literal[
    "start",
    "webhook_trigger",
    "schedule_trigger",
    "task",
    "http_request",
    "transform_mapper",
    "validator",
    "delay",
    "delay_wait",
    "decision",
    "switch_router",
    "parallel_fork",
    "join_merge",
    "loop_foreach",
    "manual_review",
    "log_event",
    "notify_alert",
    "end",
    "end_fail",
]


class Position(BaseModel):
    x: float
    y: float


class BaseNodeData(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str
    description: str | None = None
    status: str | None = None
    color: str | None = None


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    position: Position
    data: BaseNodeData


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    type: str | None = None


class WorkflowData(BaseModel):
    id: str
    name: str
    updatedAt: datetime | str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class WorkflowEnvelope(BaseModel):
    version: int = 1
    exportedAt: datetime | str
    workflow: WorkflowData


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    is_template: bool = False
    data: WorkflowData


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_template: bool | None = None
    data: WorkflowData | None = None


class WorkflowOut(BaseModel):
    id: str
    owner_id: str
    name: str
    description: str | None = None
    is_template: bool
    version: int
    data: WorkflowData
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    description: str = Field(..., min_length=3)
    mode: Literal["replace", "append"] = "replace"
    existing_workflow: WorkflowData | None = None
    name: str | None = None


class GenerateResponse(BaseModel):
    workflow: WorkflowData
