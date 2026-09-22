/**
 * MockWise Design System & Reusable Style Patterns
 *
 * Base Palette:
 * - Background: bg-slate-50 (page) / bg-white (cards/headers)
 * - Text: text-slate-900 (primary) / text-slate-500 (secondary/muted)
 * - Borders: border-slate-200 (cards/dividers) / border-slate-300 (inputs/secondary buttons)
 * - Accent: bg-indigo-600 (default) / bg-indigo-700 (hover)
 * - Font: System UI Stack (font-sans)
 */

export const buttonPrimary =
  "bg-indigo-600 text-white hover:bg-indigo-700 rounded-md px-4 py-2 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

export const buttonSecondary =
  "border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-md px-4 py-2 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

export const cardContainer =
  "bg-white border border-slate-200 rounded-lg shadow-sm p-6";

export const containerUpload = "max-w-2xl mx-auto px-4 sm:px-6 lg:px-8";
export const containerInterview = "max-w-3xl mx-auto px-4 sm:px-6 lg:px-8";
export const containerReport = "max-w-3xl mx-auto px-4 sm:px-6 lg:px-8";
