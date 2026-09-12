from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.assembler import assemble
from app.models import (
    BulletOut,
    ExperienceEntryOut,
    GenerateResumeRequest,
    GenerateResumeResponse,
    ModuleOut,
    ProjectEntryOut,
    RoleScoreOut,
)
from app.parser import get_bank, resolve_bank_path
from app.storage import save_resume

app = FastAPI(
    title="Modular Resume API",
    description=(
        "Receives a job description, classifies it against the modular resume bank's "
        "role presets, and assembles a tailored resume from the bank's vetted "
        "skill modules / experience bullets / project bank — per LAYER 3/4 rules."
    ),
    version="0.1.0",
)

# CORS_ORIGINS: comma-separated allowed origins for the frontend (e.g. the
# Next.js dev server). Defaults to the two common local dev ports so the
# bundled frontend works out of the box.
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/bank-info")
def bank_info() -> dict:
    """Confirms which modular resume bank file is actually being read, and a
    quick structural summary — the fast way to check RESUME_BANK_PATH picked
    up the right file."""
    path = resolve_bank_path()
    bank = get_bank()
    return {
        "bank_path": str(path),
        "modules": len(bank.modules),
        "bullet_banks": {k: len(v) for k, v in bank.bullet_banks.items()},
        "projects": len(bank.projects),
        "role_presets": list(bank.role_presets.keys()),
        "defensible_numbers": len(bank.facts.defensible_numbers),
        "banned_phrases": len(bank.facts.banned_phrases),
    }


@app.get("/roles")
def list_roles() -> dict:
    bank = get_bank()
    return {
        "roles": [
            {
                "name": name,
                "modules": preset.modules,
                "experience_entities": preset.experience_entities,
                "notes": preset.notes,
            }
            for name, preset in bank.role_presets.items()
        ]
    }


@app.post("/generate-resume", response_model=GenerateResumeResponse)
def generate_resume(req: GenerateResumeRequest) -> GenerateResumeResponse:
    bank = get_bank()
    contact_overrides = (
        {k: v for k, v in req.contact.model_dump().items() if v is not None}
        if req.contact
        else {}
    )
    try:
        result = assemble(
            bank,
            jd_text=req.jd,
            role_hint=req.role_hint,
            contact_overrides=contact_overrides,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_response(result, req.save_to_file)


@app.post("/generate-resume/ai")
def generate_resume_ai(req: GenerateResumeRequest) -> dict:
    """Phase 3 — deterministic assembly + CrewAI-written summary. Requires
    OPENAI_API_KEY or ANTHROPIC_API_KEY. Inactive until that's configured;
    /generate-resume above works without it."""
    from app.crew_agents import run_crew

    try:
        return run_crew(req.jd, req.role_hint)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _build_response(result, save_to_file: bool) -> GenerateResumeResponse:
    saved_path = str(save_resume(result.markdown, result.role)) if save_to_file else None
    return GenerateResumeResponse(
        role=result.role,
        role_scores=[
            RoleScoreOut(role=r.role, score=r.score, matched_keywords=r.matched_keywords, semantic_score=r.semantic_score)
            for r in result.role_scores
        ],
        modules=[ModuleOut(id=m.id, name=m.name, skills=m.skills) for m in result.modules],
        experience=[
            ExperienceEntryOut(
                entity=e.entity,
                display_title=e.display_title,
                ledger_line=e.ledger_line,
                bullets=[BulletOut(id=b.id, text=b.text) for b in e.bullets],
            )
            for e in result.experience
        ],
        projects=[
            ProjectEntryOut(
                id=p.project.id,
                name=p.project.name,
                note=p.note,
                tech=p.project.tech,
                bullets=p.project.bullets,
            )
            for p in result.projects
        ],
        education=result.education,
        education_above_experience=result.education_above_experience,
        resume_markdown=result.markdown,
        warnings=result.warnings,
        saved_path=saved_path,
    )
