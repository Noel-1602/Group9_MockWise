"use client";

import { useEffect, useState, useRef, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_BASE_URL } from "@/lib/config";

interface QuestionData {
  id: string;
  session_id: string;
  question_index: number;
  question_text: string;
  question_type: string;
}

export default function InterviewPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const resolvedParams = use(params);
  const sessionId = resolvedParams.sessionId;
  const router = useRouter();

  const [question, setQuestion] = useState<QuestionData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const playQuestionAudio = useCallback((questionId: string) => {
    try {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      const audioUrl = `${BACKEND_BASE_URL}/questions/${questionId}/audio`;
      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;

      audio.addEventListener("error", () => {
        const mediaError = audio.error;
        let message = "Failed to load audio for question.";
        if (mediaError) {
          switch (mediaError.code) {
            case 1:
              message = "Audio playback was aborted.";
              break;
            case 2:
              message = "Network error while loading audio.";
              break;
            case 3:
              message = "Failed to decode audio file.";
              break;
            case 4:
              message = "Audio format not supported or audio source unavailable.";
              break;
            default:
              message = mediaError.message || `Audio error (code ${mediaError.code}).`;
              break;
          }
        }
        setError(message);
      });

      audio.play().catch((err) => {
        console.warn("Autoplay blocked or audio failed:", err);
      });
    } catch (err) {
      console.warn("Audio playback error:", err);
    }
  }, []);

  const fetchNextQuestion = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${BACKEND_BASE_URL}/sessions/${sessionId}/questions/next`
      );

      if (res.status === 404) {
        // No more questions, interview complete
        router.push(`/report/${sessionId}`);
        return;
      }

      if (!res.ok) {
        let errMsg = "Failed to fetch next question.";
        try {
          const errData = await res.json();
          errMsg = errData.detail || errMsg;
        } catch {
          // fallback
        }
        throw new Error(errMsg);
      }

      const data: QuestionData = await res.json();
      setQuestion(data);
      playQuestionAudio(data.id);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, router, playQuestionAudio]);

  useEffect(() => {
    if (sessionId) {
      fetchNextQuestion();
    }
    return () => {
      // Cleanup media stream and audio if unmounting
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    };
  }, [sessionId, fetchNextQuestion]);

  const handleStartRecording = async () => {
    setError(null);
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Microphone recording is not supported in this browser.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? `Microphone error: ${err.message}`
          : "Microphone permission denied or unavailable.";
      setError(msg);
      setIsRecording(false);
    }
  };

  const handleStopAndSubmit = () => {
    if (!mediaRecorderRef.current || !question) return;

    const mediaRecorder = mediaRecorderRef.current;

    mediaRecorder.onstop = async () => {
      // Stop all tracks to release microphone
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }

      const mimeType = mediaRecorder.mimeType || "audio/webm";
      const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
      audioChunksRef.current = [];
      setIsRecording(false);

      if (audioBlob.size === 0) {
        setError("Recorded audio is empty. Please try recording again.");
        return;
      }

      setIsSubmitting(true);
      setError(null);

      try {
        const formData = new FormData();
        const extension = mimeType.includes("wav") ? "wav" : "webm";
        formData.append("file", audioBlob, `answer.${extension}`);

        const res = await fetch(
          `${BACKEND_BASE_URL}/questions/${question.id}/answer/audio`,
          {
            method: "POST",
            body: formData,
          }
        );

        if (!res.ok) {
          let errMsg = "Failed to submit audio answer.";
          try {
            const errData = await res.json();
            errMsg = errData.detail || errMsg;
          } catch {
            // fallback
          }
          throw new Error(errMsg);
        }

        // Successfully submitted, fetch next question
        await fetchNextQuestion();
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "Failed to submit answer.";
        setError(msg);
      } finally {
        setIsSubmitting(false);
      }
    };

    mediaRecorder.stop();
  };

  const handleSkipQuestion = async () => {
    if (!question) return;

    // Stop recording if active
    if (isRecording && mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
      setIsRecording(false);
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await fetch(
        `${BACKEND_BASE_URL}/questions/${question.id}/skip`,
        {
          method: "POST",
        }
      );

      if (!res.ok) {
        let errMsg = "Failed to skip question.";
        try {
          const errData = await res.json();
          errMsg = errData.detail || errMsg;
        } catch {
          // fallback
        }
        throw new Error(errMsg);
      }

      await fetchNextQuestion();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to skip question.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEndInterview = async () => {
    // Stop recording if active
    if (isRecording && mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
      setIsRecording(false);
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await fetch(
        `${BACKEND_BASE_URL}/sessions/${sessionId}/complete`,
        {
          method: "POST",
        }
      );

      if (!res.ok) {
        let errMsg = "Failed to end interview.";
        try {
          const errData = await res.json();
          errMsg = errData.detail || errMsg;
        } catch {
          // fallback
        }
        throw new Error(errMsg);
      }

      router.push(`/report/${sessionId}`);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to end interview.";
      setError(msg);
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <h1>Live Interview</h1>
      <p>Session ID: {sessionId}</p>

      {isLoading && <p>Loading question...</p>}

      {error && <p>Error: {error}</p>}

      {question && !isLoading && (
        <div>
          <div>
            <h2>
              Question {question.question_index + 1} ({question.question_type})
            </h2>
            <p>{question.question_text}</p>
            <button
              type="button"
              onClick={() => playQuestionAudio(question.id)}
              disabled={isSubmitting}
            >
              Play Question
            </button>
          </div>

          <div>
            {!isRecording ? (
              <button
                type="button"
                onClick={handleStartRecording}
                disabled={isSubmitting || isLoading}
              >
                Record Answer
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStopAndSubmit}
                disabled={isSubmitting}
              >
                Stop & Submit
              </button>
            )}

            {isRecording && <p>Recording in progress...</p>}
            {isSubmitting && <p>Processing...</p>}

            <button
              type="button"
              onClick={handleSkipQuestion}
              disabled={isSubmitting || isLoading}
            >
              Skip Question
            </button>
          </div>
        </div>
      )}

      <div>
        <hr />
        <button
          type="button"
          onClick={handleEndInterview}
          disabled={isSubmitting}
        >
          End Interview
        </button>
      </div>
    </div>
  );
}

