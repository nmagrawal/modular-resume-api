"use client";

import { useEffect, useState } from "react";
import { listRoles } from "@/lib/api";

export interface ComposerSubmission {
  jd: string;
  roleHint: string | null;
  useAi: boolean;
}

export default function ChatComposer({
  onSubmit,
  disabled,
}: {
  onSubmit: (submission: ComposerSubmission) => void;
  disabled: boolean;
}) {
  const [jd, setJd] = useState("");
  const [roleHint, setRoleHint] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [roles, setRoles] = useState<string[]>([]);

  useEffect(() => {
    listRoles()
      .then((data) => setRoles(data.roles.map((r) => r.name)))
      .catch(() => {
        // Backend not reachable yet — role dropdown just stays empty
        // (auto-classification still works without it).
      });
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jd.trim() || disabled) return;
    onSubmit({ jd: jd.trim(), roleHint: roleHint || null, useAi });
    setJd("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      handleSubmit(e);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-2 border-t border-neutral-200 bg-white p-3 dark:border-neutral-700 dark:bg-neutral-900"
    >
      <textarea
        value={jd}
        onChange={(e) => setJd(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Paste a job description, then press ⌘/Ctrl+Enter or click Generate…"
        rows={4}
        disabled={disabled}
        className="w-full resize-none rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-500 disabled:opacity-60 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100"
      />
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={roleHint}
          onChange={(e) => setRoleHint(e.target.value)}
          disabled={disabled}
          className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700 disabled:opacity-60 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-200"
        >
          <option value="">Auto-detect role</option>
          {roles.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-1.5 text-xs text-neutral-600 dark:text-neutral-300">
          <input
            type="checkbox"
            checked={useAi}
            onChange={(e) => setUseAi(e.target.checked)}
            disabled={disabled}
          />
          AI-written summary (needs a configured LLM on the backend)
        </label>

        <button
          type="submit"
          disabled={disabled || !jd.trim()}
          className="ml-auto rounded-lg bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {disabled ? "Generating…" : "Generate"}
        </button>
      </div>
    </form>
  );
}
