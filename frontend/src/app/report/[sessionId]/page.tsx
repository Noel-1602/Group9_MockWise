"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_BASE_URL } from "@/lib/config";
import { cardContainer } from "@/lib/styles";

interface EvaluationDetails {
  overall_score?: number;
  relevance_score?: number;
  clarity_score?: number;
  structure_score?: number;
  feedback_text?: string;
}

interface AnswerData {
  id: string;
  question_id: string;
  transcript_text?: string | null;
  score?: number | null;
  feedback_text?: string | null;
  evaluation_json?: string | null;
  skipped: boolean;
  created_at: string;
}

interface QuestionData {
  id: string;
  session_id: string;
  question_index: number;
  question_text: string;
  question_type: string;
  created_at: string;
  answer?: AnswerData | null;
}

interface SessionData {
  id: string;
  candidate_name?: string | null;
  resume_filename?: string | null;
  status: string;
  created_at: string;
  questions: QuestionData[];
  total_questions: number;
  answered_count: number;
  skipped_count: number;
  average_score?: number | null;
  resume_specific_count: number;
  general_count: number;
}

function parseEvaluationJson(jsonStr?: string | null): EvaluationDetails | null {
  if (!jsonStr) return null;
  try {
    return JSON.parse(jsonStr) as EvaluationDetails;
  } catch {
    return null;
  }
}

export default function FeedbackReportPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const resolvedParams = use(params);
  const sessionId = resolvedParams.sessionId;
  const router = useRouter();

  const [session, setSession] = useState<SessionData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSession() {
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(`${BACKEND_BASE_URL}/sessions/${sessionId}`);
        if (!res.ok) {
          let errMsg = "Failed to fetch session report.";
          try {
            const errData = await res.json();
            errMsg = errData.detail || errMsg;
          } catch {
            // fallback
          }
          throw new Error(errMsg);
        }

        const data: SessionData = await res.json();
        setSession(data);
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "An unexpected error occurred.";
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    }

    if (sessionId) {
      fetchSession();
    }
  }, [sessionId]);

  const handleStartNewInterview = () => {
    router.push("/upload");
  };

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto py-12">
        <div className={`${cardContainer} text-center py-16 space-y-4`}>
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-600 border-t-transparent" />
          <p className="text-sm font-medium text-slate-600">
            Loading session report...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-12 space-y-6">
        <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-red-700 flex items-start gap-4">
          <svg
            className="w-6 h-6 text-red-500 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <div className="flex-1 space-y-2">
            <h2 className="font-semibold text-red-800 text-lg">
              Unable to load report
            </h2>
            <p className="text-sm text-red-700">{error}</p>
            <div className="pt-2">
              <button
                type="button"
                onClick={handleStartNewInterview}
                className="bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-4 py-2 text-sm font-medium transition-colors"
              >
                Start New Interview
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="max-w-3xl mx-auto py-12">
        <div className={`${cardContainer} text-center py-12 space-y-4`}>
          <p className="text-slate-600 font-medium">No session data found.</p>
          <button
            type="button"
            onClick={handleStartNewInterview}
            className="bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-4 py-2 text-sm font-medium transition-colors"
          >
            Start New Interview
          </button>
        </div>
      </div>
    );
  }

  const sortedQuestions = [...(session.questions || [])].sort(
    (a, b) => a.question_index - b.question_index
  );

  const hasAverageScore =
    session.average_score !== null && session.average_score !== undefined;

  return (
    <div className="max-w-3xl mx-auto py-6 sm:py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Interview Report
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            {session.candidate_name ? (
              <span>
                Candidate: <strong className="text-slate-800">{session.candidate_name}</strong>
              </span>
            ) : (
              <span>Mock Interview Session</span>
            )}
            <span className="mx-2 text-slate-300">•</span>
            <span className="text-slate-400 font-mono text-xs">{session.id}</span>
          </p>
        </div>

        <button
          type="button"
          onClick={handleStartNewInterview}
          className="self-start sm:self-center bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-4 py-2 text-sm font-medium shadow-sm transition-colors"
        >
          Start New Interview
        </button>
      </div>

      {/* Summary Stat Cards */}
      <section>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {/* Average Score Card */}
          <div className={`${cardContainer} flex flex-col justify-between`}>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Average Score
            </span>
            <div className="mt-2 flex items-baseline gap-1">
              {hasAverageScore ? (
                <>
                  <span className="text-3xl font-bold text-indigo-600">
                    {session.average_score!.toFixed(1)}
                  </span>
                  <span className="text-sm font-semibold text-slate-400">/10</span>
                </>
              ) : (
                <span className="text-sm font-medium text-slate-400">
                  Not yet scored
                </span>
              )}
            </div>
          </div>

          {/* Answered Card */}
          <div className={`${cardContainer} flex flex-col justify-between`}>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Answered
            </span>
            <div className="mt-2">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {session.answered_count}
              </span>
              <span className="text-xs text-slate-400 ml-1">
                / {session.total_questions}
              </span>
            </div>
          </div>

          {/* Skipped Card */}
          <div className={`${cardContainer} flex flex-col justify-between`}>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Skipped
            </span>
            <div className="mt-2">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {session.skipped_count}
              </span>
            </div>
          </div>

          {/* Total Questions Card */}
          <div className={`${cardContainer} flex flex-col justify-between`}>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Questions
            </span>
            <div className="mt-2">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {session.total_questions}
              </span>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {session.resume_specific_count} resume • {session.general_count} general
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Questions Breakdown */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">
          Question Breakdown & Feedback
        </h2>

        {sortedQuestions.length === 0 ? (
          <div className={`${cardContainer} text-center py-8 text-slate-500 text-sm`}>
            No questions found for this session.
          </div>
        ) : (
          <div className="space-y-4">
            {sortedQuestions.map((q) => {
              const isAnswered = Boolean(q.answer && !q.answer.skipped);
              const isSkipped = Boolean(q.answer && q.answer.skipped);
              const isUnanswered = !q.answer;

              const evalData = isAnswered
                ? parseEvaluationJson(q.answer?.evaluation_json)
                : null;
              const overallScore =
                evalData?.overall_score ?? q.answer?.score ?? null;
              const feedbackText =
                evalData?.feedback_text || q.answer?.feedback_text || null;

              return (
                <div key={q.id} className={`${cardContainer} space-y-4`}>
                  {/* Top line: Index, Type, Status */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Question {q.question_index + 1}
                      </span>
                      <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded capitalize">
                        {q.question_type.replace("_", " ")}
                      </span>
                    </div>

                    {/* Visually Distinct Status Badges */}
                    {isAnswered && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                        Answered & Scored
                      </span>
                    )}

                    {isSkipped && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                        Skipped
                      </span>
                    )}

                    {isUnanswered && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                        Unanswered
                      </span>
                    )}
                  </div>

                  {/* Question Text */}
                  <p className="text-base sm:text-lg font-medium text-slate-900 leading-snug">
                    {q.question_text}
                  </p>

                  {/* Answered Details */}
                  {isAnswered && (
                    <div className="space-y-4 pt-2 border-t border-slate-100">
                      {/* Transcript */}
                      <div className="bg-slate-50 border border-slate-200/70 rounded-lg p-3.5 space-y-1">
                        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                          Your Answer (Transcript)
                        </span>
                        <p className="text-sm text-slate-800 italic leading-relaxed">
                          &ldquo;{q.answer?.transcript_text || "(No transcript recorded)"}&rdquo;
                        </p>
                      </div>

                      {/* Scores */}
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="bg-indigo-50 border border-indigo-100 text-indigo-950 px-3 py-1.5 rounded-md text-sm font-semibold inline-flex items-center gap-1.5">
                          <span>Overall Score:</span>
                          <span className="text-indigo-600 font-bold text-base">
                            {overallScore !== null && overallScore !== undefined
                              ? overallScore
                              : "N/A"}
                          </span>
                          <span className="text-xs text-indigo-400">/10</span>
                        </div>

                        {evalData && (
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="bg-slate-100 text-slate-700 px-2.5 py-1 rounded border border-slate-200">
                              Relevance: <strong>{evalData.relevance_score ?? "N/A"}/10</strong>
                            </span>
                            <span className="bg-slate-100 text-slate-700 px-2.5 py-1 rounded border border-slate-200">
                              Clarity: <strong>{evalData.clarity_score ?? "N/A"}/10</strong>
                            </span>
                            <span className="bg-slate-100 text-slate-700 px-2.5 py-1 rounded border border-slate-200">
                              Structure: <strong>{evalData.structure_score ?? "N/A"}/10</strong>
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Feedback */}
                      {feedbackText && (
                        <div className="bg-indigo-50/40 border border-indigo-100/70 rounded-lg p-3.5 space-y-1">
                          <span className="text-xs font-semibold text-indigo-900 uppercase tracking-wider">
                            AI Feedback
                          </span>
                          <p className="text-sm text-slate-700 leading-relaxed">
                            {feedbackText}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Bottom CTA */}
      <div className="pt-4 text-center">
        <button
          type="button"
          onClick={handleStartNewInterview}
          className="bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-6 py-3 font-medium text-sm shadow-sm transition-colors w-full sm:w-auto"
        >
          Start New Interview
        </button>
      </div>
    </div>
  );
}
