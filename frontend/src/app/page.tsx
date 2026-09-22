import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { cardContainer } from "@/lib/styles";

export default function Home() {
  return (
    <AppShell size="3xl" className="py-12 sm:py-16">
      {/* Hero Section */}
      <section className="text-center space-y-6">
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-slate-900">
          Ace Your Placement Interview with AI
        </h1>
        <p className="text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed">
          Practice real interview questions generated from your resume, get instant
          AI feedback.
        </p>

        {/* CTA and Demo Link */}
        <div className="pt-4 flex flex-col items-center justify-center gap-3">
          <Link
            href="/upload"
            className="inline-flex items-center justify-center bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-6 py-3 font-medium text-base shadow-sm transition-colors w-full sm:w-auto"
          >
            Start Mock Interview
          </Link>
          <Link
            href="/report/c414c078-8f3e-430a-a6b6-8f1fc1105021"
            className="text-sm font-medium text-slate-500 hover:text-indigo-600 transition-colors underline decoration-slate-300 underline-offset-4 hover:decoration-indigo-600"
          >
            View a sample report &rarr;
          </Link>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section className="mt-16 sm:mt-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className={cardContainer}>
            <h2 className="text-base font-semibold text-slate-900 mb-2">
              Personalized Questions
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Generated from your actual resume and project experience.
            </p>
          </div>

          <div className={cardContainer}>
            <h2 className="text-base font-semibold text-slate-900 mb-2">
              Speak Your Answers
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Real voice-based mock interview with speech synthesis, not typing.
            </p>
          </div>

          <div className={cardContainer}>
            <h2 className="text-base font-semibold text-slate-900 mb-2">
              Instant Feedback
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">
              Get scored on relevance, clarity, and structure with actionable insights.
            </p>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
