from __future__ import annotations

from pydantic import BaseModel, Field


class ContactOverrides(BaseModel):
    name: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    site: str | None = None


class GenerateResumeRequest(BaseModel):
    jd: str = Field(..., min_length=20, description="The job description text.")
    role_hint: str | None = Field(
        None, description="Force a specific role preset instead of auto-classifying the JD."
    )
    contact: ContactOverrides | None = None
    save_to_file: bool = Field(
        False, description="If true, also write the assembled markdown to app/output/."
    )


class RoleScoreOut(BaseModel):
    role: str
    score: int
    matched_keywords: list[str]
    semantic_score: float = 0.0


class BulletOut(BaseModel):
    id: str
    text: str


class ExperienceEntryOut(BaseModel):
    entity: str
    display_title: str
    ledger_line: str | None
    bullets: list[BulletOut]


class ProjectEntryOut(BaseModel):
    id: str
    name: str
    note: str | None
    tech: list[str]
    bullets: list[str]


class ModuleOut(BaseModel):
    id: str
    name: str
    skills: list[str]


class GenerateResumeResponse(BaseModel):
    role: str
    role_scores: list[RoleScoreOut]
    modules: list[ModuleOut]
    experience: list[ExperienceEntryOut]
    projects: list[ProjectEntryOut]
    education: list[str]
    education_above_experience: bool
    resume_markdown: str
    warnings: list[str]
    saved_path: str | None = None
