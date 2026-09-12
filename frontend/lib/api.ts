// Typed client for the Modular Resume API (see ../../backend/app/models.py —
// keep these in sync with GenerateResumeResponse et al.).

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export interface RoleScore {
  role: string;
  score: number;
  matched_keywords: string[];
  semantic_score: number;
}

export interface Bullet {
  id: string;
  text: string;
}

export interface ExperienceEntry {
  entity: string;
  display_title: string;
  ledger_line: string | null;
  bullets: Bullet[];
}

export interface ProjectEntry {
  id: string;
  name: string;
  note: string | null;
  tech: string[];
  bullets: string[];
}

export interface ModuleOut {
  id: string;
  name: string;
  skills: string[];
}

export interface GenerateResumeResponse {
  role: string;
  role_scores: RoleScore[];
  modules: ModuleOut[];
  experience: ExperienceEntry[];
  projects: ProjectEntry[];
  education: string[];
  education_above_experience: boolean;
  resume_markdown: string;
  warnings: string[];
  saved_path: string | null;
}

export interface GenerateResumeAiResponse {
  role: string;
  resume_markdown: string;
  ai_summary: string;
  ai_summary_raw: string;
  warnings: string[];
}

export interface ContactOverrides {
  name?: string;
  location?: string;
  email?: string;
  phone?: string;
  linkedin?: string;
  github?: string;
  site?: string;
}

export interface GenerateResumeRequest {
  jd: string;
  role_hint?: string | null;
  contact?: ContactOverrides;
  save_to_file?: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      `Could not reach the backend at ${API_BASE_URL}. Is it running? (uvicorn app.main:app --port 8000)`,
      0,
    );
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(detail, res.status);
  }

  return res.json();
}

export function generateResume(req: GenerateResumeRequest) {
  return postJson<GenerateResumeResponse>("/generate-resume", req);
}

export function generateResumeAi(req: GenerateResumeRequest) {
  return postJson<GenerateResumeAiResponse>("/generate-resume/ai", req);
}

export interface RolesResponse {
  roles: { name: string; modules: string[]; experience_entities: string[]; notes: string[] }[];
}

export async function listRoles(): Promise<RolesResponse> {
  const res = await fetch(`${API_BASE_URL}/roles`);
  if (!res.ok) throw new ApiError(res.statusText, res.status);
  return res.json();
}
