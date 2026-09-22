"use client";

import { useEffect, useState, useRef, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_BASE_URL } from "@/lib/config";
import { cardContainer } from "@/lib/styles";

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
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [liveTranscript, setLiveTranscript] = useState<{ final: string; interim: string }>({
    final: "",
    interim: "",
  });
  const [hasSpeechRecognitionSupport, setHasSpeechRecognitionSupport] = useState<boolean>(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const recognitionRef = useRef<any>(null);
  // TODO: restore once Piper is wired
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const isSupported = Boolean(
        (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition ||
        (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition
      );
      setHasSpeechRecognitionSupport(isSupported);
    }
  }, []);

  // Temporary frontend-only TTS shim using window.speechSynthesis for demo purposes
  const speakQuestion = useCallback((text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setError("Speech synthesis is not supported in this browser.");
      return;
    }

    try {
      // Cancel any ongoing speech before starting a new one
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      currentUtteranceRef.current = utterance;

      utterance.onstart = () => {
        setIsPlayingAudio(true);
        setError(null);
      };

      utterance.onend = () => {
        setIsPlayingAudio(false);
      };

      utterance.onerror = (event) => {
        setIsPlayingAudio(false);
        // "canceled" or "interrupted" events occur normally when window.speechSynthesis.cancel() is invoked
        if (event.error !== "canceled" && event.error !== "interrupted") {
          setError(`Speech synthesis error: ${event.error || "Playback failed"}`);
        }
      };

      window.speechSynthesis.speak(utterance);
    } catch (err: unknown) {
      setIsPlayingAudio(false);
      const msg =
        err instanceof Error ? err.message : "Failed to synthesize speech.";
      setError(msg);
    }
  }, []);

  // TODO: restore once Piper is wired
  // const playQuestionAudio = useCallback((questionId: string) => {
  //   try {
  //     if (audioPlayerRef.current) {
  //       audioPlayerRef.current.pause();
  //     }
  //     const audioUrl = `${BACKEND_BASE_URL}/questions/${questionId}/audio`;
  //     const audio = new Audio(audioUrl);
  //     audioPlayerRef.current = audio;
  //
  //     audio.addEventListener("play", () => setIsPlayingAudio(true));
  //     audio.addEventListener("ended", () => setIsPlayingAudio(false));
  //     audio.addEventListener("pause", () => setIsPlayingAudio(false));
  //
  //     audio.addEventListener("error", () => {
  //       setIsPlayingAudio(false);
  //       const mediaError = audio.error;
  //       let message = "Failed to load audio for question.";
  //       if (mediaError) {
  //         switch (mediaError.code) {
  //           case 1:
  //             message = "Audio playback was aborted.";
  //             break;
  //           case 2:
  //             message = "Network error while loading audio.";
  //             break;
  //           case 3:
  //             message = "Failed to decode audio file.";
  //             break;
  //           case 4:
  //             message = "Audio format not supported or audio source unavailable.";
  //             break;
  //           default:
  //             message = mediaError.message || `Audio error (code ${mediaError.code}).`;
  //             break;
  //         }
  //       }
  //       setError(message);
  //     });
  //
  //     audio.play().catch((err) => {
  //       setIsPlayingAudio(false);
  //       console.warn("Autoplay blocked or audio failed:", err);
  //     });
  //   } catch (err) {
  //     setIsPlayingAudio(false);
  //     console.warn("Audio playback error:", err);
  //   }
  // }, []);

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
      setLiveTranscript({ final: "", interim: "" });
      // TODO: restore once Piper is wired
      // playQuestionAudio(data.id);
      speakQuestion(data.question_text);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, router, speakQuestion]);

  useEffect(() => {
    if (sessionId) {
      fetchNextQuestion();
    }
    return () => {
      // Cleanup media stream, speech synthesis, and live recognition if unmounting
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
      // TODO: restore once Piper is wired
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    };
  }, [sessionId, fetchNextQuestion]);

  const handleStartRecording = async () => {
    // Stop any ongoing speech
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);
    setError(null);
    setLiveTranscript({ final: "", interim: "" });

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

      // Start live speech recognition if supported (temporary frontend preview)
      if (typeof window !== "undefined") {
        const SpeechRecognitionClass =
          (window as any).SpeechRecognition ||
          (window as any).webkitSpeechRecognition;

        if (SpeechRecognitionClass) {
          try {
            const recognition = new SpeechRecognitionClass();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = "en-US";

            recognition.onresult = (event: any) => {
              let finalTranscript = "";
              let interimTranscript = "";

              for (let i = 0; i < event.results.length; ++i) {
                const item = event.results[i];
                const piece = item[0]?.transcript || "";
                if (item.isFinal) {
                  finalTranscript += (finalTranscript ? " " : "") + piece.trim();
                } else {
                  interimTranscript += (interimTranscript ? " " : "") + piece;
                }
              }

              setLiveTranscript({
                final: finalTranscript,
                interim: interimTranscript,
              });
            };

            recognition.onerror = (event: any) => {
              // Non-fatal recognition errors (e.g. no-speech, aborted) should not break actual recording
              console.warn("SpeechRecognition event:", event.error);
            };

            recognition.onend = () => {
              // Recognition ended
            };

            recognition.start();
            recognitionRef.current = recognition;
          } catch (recErr) {
            console.warn("Could not start live SpeechRecognition:", recErr);
          }
        }
      }
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

    // Stop any ongoing speech
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);

    // Stop live recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }

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

    // Stop any ongoing speech
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);

    // Stop live recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
    setLiveTranscript({ final: "", interim: "" });

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
    // Stop any ongoing speech
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);

    // Stop live recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
    setLiveTranscript({ final: "", interim: "" });

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

  const currentQuestionNum = question ? question.question_index + 1 : 1;
  const progressPercent = question
    ? Math.min(100, Math.max(15, (currentQuestionNum / 5) * 100))
    : 10;

  return (
    <div className="max-w-3xl mx-auto py-6 sm:py-8 space-y-6">
      {/* Top Header: Progress & End Interview */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500">
            <span>Question {currentQuestionNum}</span>
            {question && (
              <span className="capitalize text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                {question.question_type.replace("_", " ")}
              </span>
            )}
          </div>
          <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-600 rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        <button
          type="button"
          onClick={handleEndInterview}
          disabled={isSubmitting}
          className="shrink-0 text-xs sm:text-sm font-medium text-slate-500 hover:text-red-600 hover:bg-red-50/50 px-3 py-1.5 rounded-md transition-colors disabled:opacity-50"
        >
          End Interview
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-start gap-3">
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
            <p className="font-medium text-red-800">Error</p>
            <p className="mt-0.5 text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && !question && (
        <div className={`${cardContainer} text-center py-16 space-y-4`}>
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-600 border-t-transparent" />
          <p className="text-sm font-medium text-slate-600">
            Loading next question...
          </p>
        </div>
      )}

      {/* Question Card */}
      {question && (
        <div className={`${cardContainer} space-y-6`}>
          <div className="space-y-4">
            <p className="text-xl sm:text-2xl font-medium text-slate-900 leading-relaxed">
              {question.question_text}
            </p>

            {/* Audio playback controls */}
            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => speakQuestion(question.question_text)}
                disabled={isSubmitting}
                className="inline-flex items-center gap-2 border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
              >
                <svg
                  className="w-4 h-4 text-indigo-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                </svg>
                Play Question
              </button>

              {isPlayingAudio && (
                <div className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full animate-pulse">
                  <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
                  Playing Audio...
                </div>
              )}
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Interactive Core: Mic Record / Stop Section */}
          <div className="py-6 flex flex-col items-center justify-center space-y-4 text-center">
            {/* Main Record/Stop Button */}
            {!isRecording ? (
              <button
                type="button"
                onClick={handleStartRecording}
                disabled={isSubmitting || isLoading}
                className="group relative w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white shadow-md hover:shadow-lg flex flex-col items-center justify-center transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-4 focus:ring-indigo-500/30"
              >
                <svg
                  className="w-8 h-8 sm:w-9 sm:h-9"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
                <span className="text-[10px] sm:text-xs font-medium mt-1">Record</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStopAndSubmit}
                disabled={isSubmitting}
                className="group relative w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg flex flex-col items-center justify-center transition-all transform hover:scale-105 active:scale-95 ring-4 ring-red-300 animate-pulse focus:outline-none"
              >
                <div className="w-6 h-6 sm:w-7 sm:h-7 bg-white rounded-sm" />
                <span className="text-[10px] sm:text-xs font-medium mt-1">Stop</span>
              </button>
            )}

            {/* Status Messages */}
            <div className="h-6 flex items-center justify-center">
              {isRecording && (
                <div className="flex items-center gap-2 text-sm font-medium text-red-600">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-ping" />
                  Recording in progress... Click Stop to submit
                </div>
              )}
              {isSubmitting && (
                <div className="flex items-center gap-2 text-sm font-medium text-indigo-600">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-indigo-600 border-t-transparent" />
                  Processing answer...
                </div>
              )}
              {!isRecording && !isSubmitting && (
                <p className="text-xs text-slate-500">
                  Click the microphone when you are ready to answer
                </p>
              )}
            </div>

            {/* Live Transcription Preview (Client-side SpeechRecognition) */}
            {(isRecording || (isSubmitting && (liveTranscript.final || liveTranscript.interim))) && hasSpeechRecognitionSupport && (
              <div className="w-full max-w-lg mx-auto p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-left shadow-sm transition-all">
                <div className="flex items-center justify-between gap-2 mb-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <span className="flex items-center gap-1.5 text-indigo-600">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        isRecording ? "bg-indigo-600 animate-pulse" : "bg-slate-400"
                      }`}
                    />
                    Live preview (your device)
                  </span>
                  <span className="text-[10px] text-slate-400 font-normal lowercase">
                    (local preview only)
                  </span>
                </div>
                {liveTranscript.final || liveTranscript.interim ? (
                  <p className="text-sm text-slate-800 leading-relaxed break-words">
                    <span>{liveTranscript.final}</span>
                    {liveTranscript.final && liveTranscript.interim && <span> </span>}
                    <span className="text-slate-400 italic">{liveTranscript.interim}</span>
                  </p>
                ) : (
                  <p className="text-xs text-slate-400 italic">
                    Listening... Start speaking to see live transcription preview
                  </p>
                )}
              </div>
            )}

            {/* Skip Button - positioned separately */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleSkipQuestion}
                disabled={isSubmitting || isLoading}
                className="text-xs sm:text-sm font-medium text-slate-500 hover:text-slate-800 border border-slate-200 hover:border-slate-300 hover:bg-slate-50 px-4 py-2 rounded-md transition-colors disabled:opacity-50"
              >
                Skip Question &rarr;
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
