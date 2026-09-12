import type { GenerateResumeResponse, GenerateResumeAiResponse } from "@/lib/api";
import SectionBox from "./SectionBox";
import CopyButton from "./CopyButton";

function skillsAsText(result: GenerateResumeResponse): string {
  return result.modules.map((m) => `${m.name}: ${m.skills.join(", ")}`).join("\n");
}

function experienceAsText(result: GenerateResumeResponse): string {
  return result.experience
    .map((e) => {
      const header = e.ledger_line ? `${e.display_title} (${e.ledger_line})` : e.display_title;
      const bullets = e.bullets.map((b) => `- ${b.text}`).join("\n");
      return `${header}\n${bullets}`;
    })
    .join("\n\n");
}

function projectsAsText(result: GenerateResumeResponse): string {
  return result.projects
    .map((p) => {
      const title = p.note ? `${p.name} (${p.note})` : p.name;
      const tech = p.tech.length ? `[${p.tech.join(", ")}]\n` : "";
      const bullets = p.bullets.map((b) => `- ${b}`).join("\n");
      return `${title}\n${tech}${bullets}`;
    })
    .join("\n\n");
}

function educationAsText(result: GenerateResumeResponse): string {
  return result.education.map((e) => `- ${e}`).join("\n");
}

export default function ResumeResult({
  result,
  aiResult,
}: {
  result: GenerateResumeResponse;
  aiResult?: GenerateResumeAiResponse;
}) {
  const topScore = result.role_scores[0];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600 dark:border-neutral-700 dark:bg-neutral-800/50 dark:text-neutral-300">
        <span className="font-semibold text-neutral-800 dark:text-neutral-100">{result.role}</span>
        {topScore && (
          <span>
            matched keywords: {topScore.matched_keywords.length ? topScore.matched_keywords.join(", ") : "none"}
          </span>
        )}
      </div>

      {result.warnings.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
          {result.warnings.map((w, i) => (
            <p key={i}>⚠ {w}</p>
          ))}
        </div>
      )}

      {aiResult && (
        <SectionBox title="Summary (AI-generated)" copyText={aiResult.ai_summary}>
          <p className="whitespace-pre-wrap">{aiResult.ai_summary}</p>
        </SectionBox>
      )}

      <SectionBox title="Skills" copyText={skillsAsText(result)}>
        <div className="flex flex-col gap-1">
          {result.modules.map((m) => (
            <p key={m.id}>
              <span className="font-medium">{m.name}:</span> {m.skills.join(" · ")}
            </p>
          ))}
        </div>
      </SectionBox>

      <SectionBox title="Experience" copyText={experienceAsText(result)}>
        <div className="flex flex-col gap-3">
          {result.experience.map((e) => (
            <div key={e.entity}>
              <p className="font-medium">
                {e.display_title}
                {e.ledger_line && <span className="font-normal text-neutral-500"> ({e.ledger_line})</span>}
              </p>
              <ul className="list-disc pl-5">
                {e.bullets.map((b) => (
                  <li key={b.id}>{b.text}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </SectionBox>

      <SectionBox title="Projects" copyText={projectsAsText(result)}>
        <div className="flex flex-col gap-3">
          {result.projects.map((p) => (
            <div key={p.id}>
              <p className="font-medium">
                {p.name}
                {p.note && <span className="font-normal text-neutral-500"> ({p.note})</span>}
              </p>
              {p.tech.length > 0 && (
                <p className="font-mono text-xs text-neutral-500">{p.tech.join(" · ")}</p>
              )}
              <ul className="list-disc pl-5">
                {p.bullets.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </SectionBox>

      <SectionBox title="Education" copyText={educationAsText(result)}>
        <ul className="list-disc pl-5">
          {result.education.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </SectionBox>

      <div className="rounded-lg border border-neutral-200 bg-white dark:border-neutral-700 dark:bg-neutral-900">
        <div className="flex items-center justify-between border-b border-neutral-200 px-3 py-2 dark:border-neutral-700">
          <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">Full resume (Markdown)</h3>
          <CopyButton text={result.resume_markdown} />
        </div>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap px-3 py-2 text-xs text-neutral-700 dark:text-neutral-200">
          {result.resume_markdown}
        </pre>
      </div>
    </div>
  );
}
