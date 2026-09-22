"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_BASE_URL } from "@/lib/config";

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
      <div>
        <h1>Feedback Report</h1>
        <p>Loading session report...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1>Feedback Report</h1>
        <p>Error: {error}</p>
        <button type="button" onClick={handleStartNewInterview}>
          Start New Interview
        </button>
      </div>
    );
  }

  if (!session) {
    return (
      <div>
        <h1>Feedback Report</h1>
        <p>No session data found.</p>
        <button type="button" onClick={handleStartNewInterview}>
          Start New Interview
        </button>
      </div>
    );
  }

  const sortedQuestions = [...(session.questions || [])].sort(
    (a, b) => a.question_index - b.question_index
  );

  return (
    <div>
      <h1>Feedback Report</h1>
      <p>Session ID: {session.id}</p>
      {session.candidate_name && <p>Candidate: {session.candidate_name}</p>}

      <section>
        <h2>Session Summary</h2>
        <div>
          <p>
            <strong>Average Score: </strong>
            {session.average_score !== null && session.average_score !== undefined
              ? session.average_score.toFixed(1)
              : "Not enough data"}
          </p>
          <p>
            <strong>Questions Answered: </strong>
            {session.answered_count} / {session.total_questions}
          </p>
          <p>
            <strong>Questions Skipped: </strong>
            {session.skipped_count}
          </p>
          <p>
            <strong>Question Breakdown: </strong>
            {session.resume_specific_count} resume-specific / {session.general_count} general
          </p>
        </div>
      </section>

      <hr />

      <section>
        <h2>Question Breakdown & Feedback</h2>
        {sortedQuestions.length === 0 ? (
          <p>No questions found for this session.</p>
        ) : (
          <div>
            {sortedQuestions.map((q) => {
              const isAnswered = q.answer && !q.answer.skipped;
              const isSkipped = q.answer && q.answer.skipped;
              const isUnanswered = !q.answer;

              const evalData = isAnswered
                ? parseEvaluationJson(q.answer?.evaluation_json)
                : null;
              const overallScore =
                evalData?.overall_score ?? q.answer?.score ?? null;
              const feedbackText =
                evalData?.feedback_text || q.answer?.feedback_text || null;

              return (
                <div key={q.id}>
                  <h3>
                    Question {q.question_index + 1}: {q.question_text}
                  </h3>
                  <p>
                    <strong>Type:</strong> {q.question_type}
                  </p>

                  {isSkipped && (
                    <p>
                      <strong>Status:</strong> Skipped
                    </p>
                  )}

                  {isUnanswered && (
                    <p>
                      <strong>Status:</strong> Not answered
                    </p>
                  )}

                  {isAnswered && (
                    <div>
                      <p>
                        <strong>Status:</strong> Answered
                      </p>
                      <p>
                        <strong>Transcript:</strong>{" "}
                        {q.answer?.transcript_text || "(No transcript available)"}
                      </p>
                      <p>
                        <strong>Overall Score:</strong>{" "}
                        {overallScore !== null && overallScore !== undefined
                          ? overallScore
                          : "N/A"}
                      </p>

                      {evalData && (
                        <div>
                          <p>
                            <strong>Sub-scores:</strong>
                          </p>
                          <ul>
                            <li>
                              Relevance:{" "}
                              {evalData.relevance_score !== undefined
                                ? evalData.relevance_score
                                : "N/A"}
                            </li>
                            <li>
                              Clarity:{" "}
                              {evalData.clarity_score !== undefined
                                ? evalData.clarity_score
                                : "N/A"}
                            </li>
                            <li>
                              Structure:{" "}
                              {evalData.structure_score !== undefined
                                ? evalData.structure_score
                                : "N/A"}
                            </li>
                          </ul>
                        </div>
                      )}

                      {feedbackText && (
                        <p>
                          <strong>Feedback:</strong> {feedbackText}
                        </p>
                      )}
                    </div>
                  )}
                  <hr />
                </div>
              );
            })}
          </div>
        )}
      </section>

      <div>
        <button type="button" onClick={handleStartNewInterview}>
          Start New Interview
        </button>
      </div>
    </div>
  );
}
