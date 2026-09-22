"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_BASE_URL } from "@/lib/config";
import { cardContainer } from "@/lib/styles";

export default function UploadPage() {
  const router = useRouter();
  const [candidateName, setCandidateName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!candidateName.trim()) {
      setError("Please enter candidate name.");
      return;
    }
    if (!file) {
      setError("Please select a resume file (.pdf or .docx).");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 1. Create session
      const sessionRes = await fetch(`${BACKEND_BASE_URL}/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          candidate_name: candidateName.trim(),
          resume_filename: file.name,
        }),
      });

      if (!sessionRes.ok) {
        let errMsg = "Failed to create session";
        try {
          const errData = await sessionRes.json();
          errMsg = errData.detail || errMsg;
        } catch {
          // fallback to default error message
        }
        throw new Error(errMsg);
      }

      const sessionData = await sessionRes.json();
      const sessionId = sessionData.id;

      // 2. Upload resume
      const formData = new FormData();
      formData.append("file", file);

      const resumeRes = await fetch(
        `${BACKEND_BASE_URL}/sessions/${sessionId}/resume`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!resumeRes.ok) {
        let errMsg = "Failed to upload resume";
        try {
          const errData = await resumeRes.json();
          errMsg = errData.detail || errMsg;
        } catch {
          // fallback to default error message
        }
        throw new Error(errMsg);
      }

      // Navigate to interview page on success
      router.push(`/interview/${sessionId}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-8 sm:py-12">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          Start Your Mock Interview
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Upload your resume to generate personalized interview questions.
        </p>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-start gap-3">
          <svg
            className="w-5 h-5 text-red-500 shrink-0 mt-0.5"
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
          <div className="flex-1">
            <p className="font-medium text-red-800">Upload Failed</p>
            <p className="mt-0.5 text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Form Card */}
      <div className={cardContainer}>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label
              htmlFor="candidate-name"
              className="block text-sm font-medium text-slate-700 mb-1"
            >
              Candidate Name
            </label>
            <input
              id="candidate-name"
              type="text"
              placeholder="e.g. Alex Johnson"
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              disabled={isLoading}
              required
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-slate-100 disabled:text-slate-500 transition-colors"
            />
          </div>

          <div>
            <label
              htmlFor="resume-file"
              className="block text-sm font-medium text-slate-700 mb-1"
            >
              Resume (.pdf, .docx)
            </label>
            <div className="relative border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-lg p-6 text-center transition-colors bg-slate-50/50">
              <input
                id="resume-file"
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    setFile(e.target.files[0]);
                  } else {
                    setFile(null);
                  }
                }}
                disabled={isLoading}
                required
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
              />
              <div className="space-y-2">
                <svg
                  className="mx-auto h-8 w-8 text-slate-400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                {file ? (
                  <div className="text-sm font-medium text-indigo-600 break-all">
                    {file.name}
                  </div>
                ) : (
                  <>
                    <div className="text-sm font-medium text-slate-700">
                      Click to upload PDF or DOCX
                    </div>
                    <div className="text-xs text-slate-500">
                      PDF or Word documents up to 10MB
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-4 py-2.5 font-medium text-sm shadow-sm transition-colors disabled:opacity-75 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Generating your questions...
                </>
              ) : (
                "Start Interview"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
