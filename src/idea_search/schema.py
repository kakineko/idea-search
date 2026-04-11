"""Schema definitions for Idea Search."""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProblemInput(BaseModel):
    problem: str
    constraints: List[str] = Field(default_factory=list)
    context: Optional[str] = None


class Idea(BaseModel):
    id: str
    round: int
    role: str
    title: str
    statement: str
    rationale: str
    tags: List[str] = Field(default_factory=list)
    parent_ids: List[str] = Field(default_factory=list)
    cliche_flag: bool = False
    cliche_reason: Optional[str] = None
    similar_to: List[str] = Field(default_factory=list)

    def to_text(self) -> str:
        return f"{self.title}. {self.statement}"


class AxisEvaluation(BaseModel):
    score: float  # 0-5
    rationale: str
    suggestion: str


class Evaluation(BaseModel):
    idea_id: str
    novelty: AxisEvaluation
    feasibility: AxisEvaluation
    value: AxisEvaluation
    risk: AxisEvaluation  # higher = more risky

    def composite(self) -> float:
        return (
            self.novelty.score
            + self.feasibility.score
            + self.value.score
            - self.risk.score
        )


class EvaluatedIdea(BaseModel):
    idea: Idea
    evaluation: Evaluation


class Cluster(BaseModel):
    label: str
    member_ids: List[str]


class FinalReport(BaseModel):
    problem: str
    rounds: int
    total_ideas: int
    clusters: List[Cluster]
    top_per_cluster: List[Dict[str, Any]]
    cliche_patterns_detected: List[str]
    summary: str
