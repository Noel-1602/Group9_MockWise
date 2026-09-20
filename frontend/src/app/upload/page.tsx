"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_BASE_URL } from "@/lib/config";

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
    <div>
      <h1>Upload Resume</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="candidate-name">Candidate Name: </label>
          <input
            id="candidate-name"
            type="text"
            value={candidateName}
            onChange={(e) => setCandidateName(e.target.value)}
            disabled={isLoading}
            required
          />
        </div>

        <div>
          <label htmlFor="resume-file">Resume (.pdf, .docx): </label>
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
          />
        </div>

        <div>
          <button type="submit" disabled={isLoading}>
            {isLoading ? "Starting..." : "Start Interview"}
          </button>
        </div>
      </form>

      {isLoading && <p>Creating session and uploading resume...</p>}
      {error && <p>Error: {error}</p>}
    </div>
  );
}

