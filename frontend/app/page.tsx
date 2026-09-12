"use client";

import { useState } from "react";
import ChatComposer, { ComposerSubmission } from "@/components/ChatComposer";
import ResumeResult from "@/components/ResumeResult";
import {
  generateResume,
  generateResumeAi,
  GenerateResumeResponse,
  GenerateResumeAiResponse,
  ApiError,
} from "@/lib/api";

interface Turn {
  id: number;
  jd: string;
  status: "loading" | "done" | "error";
  result?: GenerateResumeResponse;
  aiResult?: GenerateResumeAiResponse;
  aiError?: string;
  error?: string;
}

let nextId = 1;

export default function Home() {
  const [turns, setTurns] = useState<Turn[]>([]);

  async function handleSubmit({ jd, roleHint, useAi }: ComposerSubmission) {
    const id = nextId++;
    setTurns((prev) => [...prev, { id, jd, status: "loading" }]);

    try {
      const result = await generateResume({ jd, role_hint: roleHint });

      let aiResult: GenerateResumeAiResponse | undefined;
      let aiError: string | undefined;
      if (useAi) {
        try {
          aiResult = await generateResumeAi({ jd, role_hint: roleHint });
        } catch (e) {
          aiError = e instanceof ApiError ? e.message : "AI summary request failed.";
        }
      }

      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: "done", result, aiResult, aiError } : t)),
      );
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Something went wrong.";
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: "error", error: message } : t)));
    }
  }

  const isGenerating = turns.some((t) => t.status === "loading");

  return (
    <div className="flex h-dvh flex-col bg-neutral-50 dark:bg-neutral-950">
      <header className="border-b border-neutral-200 bg-white px-4 py-3 dark:border-neutral-700 dark:bg-neutral-900">
        <h1 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">Modular Resume Chat</h1>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          Paste a job description — get a resume assembled from your modular resume bank.
        </p>
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <div className="mx-auto mt-16 max-w-md text-center text-sm text-neutral-400 dark:text-neutral-500">
            No messages yet — paste a job description below to generate your first resume.
          </div>
        )}

        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {turns.map((turn) => (
            <div key={turn.id} className="flex flex-col gap-2">
              {/* user message */}
              <div className="self-end max-w-[80%] rounded-2xl rounded-br-sm bg-neutral-900 px-4 py-2 text-sm whitespace-pre-wrap text-white dark:bg-neutral-100 dark:text-neutral-900">
                {turn.jd}
              </div>

              {/* assistant response */}
              <div className="max-w-full">
                {turn.status === "loading" && (
                  <div className="w-fit rounded-2xl rounded-bl-sm bg-white px-4 py-2 text-sm text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
                    Generating…
                  </div>
                )}
                {turn.status === "error" && (
                  <div className="w-fit rounded-2xl rounded-bl-sm border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
                    {turn.error}
                  </div>
                )}
                {turn.status === "done" && turn.result && (
                  <div className="flex flex-col gap-2">
                    <ResumeResult result={turn.result} aiResult={turn.aiResult} />
                    {turn.aiError && (
                      <p className="text-xs text-amber-600 dark:text-amber-400">
                        AI summary unavailable: {turn.aiError}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </main>

      <div className="mx-auto w-full max-w-3xl">
        <ChatComposer onSubmit={handleSubmit} disabled={isGenerating} />
      </div>
    </div>
  );
}
