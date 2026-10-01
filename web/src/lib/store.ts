import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { ReviewState } from "./review";
import type { AnalysisReport, Details, ProposalsResult, TailorResult } from "./types";

export const STEPS = [
  { id: "upload", label: "Upload" },
  { id: "details", label: "Check details" },
  { id: "review", label: "Review" },
  { id: "results", label: "Results" },
] as const;

export type StepId = (typeof STEPS)[number]["id"];
// "report" is the "just check my match" page, outside the four steps.
export type View = StepId | "report";
export type Intent = "tailor" | "check";
export type Template = "ats" | "keep";

/** This visit's run. Kept in memory only: the server holds the real state,
 *  and a resume never goes into browser storage. */
export interface Run {
  intent: Intent;
  file: File | null;
  jdText: string;
  template: Template;
  details: Details | null;
  parseIssues: string[];
  report: AnalysisReport | null;
  drafted: ProposalsResult | null;
  review: ReviewState | null; // decisions on the drafted proposals, kept across Back
  results: TailorResult | null;
  resultsVersion: number; // changes per tailoring run, so previews reload
}

export const EMPTY_RUN: Run = {
  intent: "tailor", file: null, jdText: "", template: "ats", details: null, parseIssues: [],
  report: null, drafted: null, review: null, results: null, resultsVersion: 0,
};
export type Theme = "dark" | "light" | "system";

export interface Settings {
  model: string | null; // null: the provider's default
  strictFactual: boolean;
  rememberAnswers: boolean;
  theme: Theme;
}

interface AppState {
  step: View;
  // Furthest step reached in this run; the stepper lets you go back to any
  // step up to it, never forward past it.
  reached: number;
  settings: Settings;
  run: Run;
  running: boolean; // a long step is in flight (see lib/inflight.ts)
  goTo: (step: StepId) => void;
  advance: (step: View) => void;
  updateRun: (patch: Partial<Run>) => void;
  restart: () => void;
  updateSettings: (patch: Partial<Settings>) => void;
}

export const stepIndex = (step: View) => STEPS.findIndex((s) => s.id === step);

const THEMES: Theme[] = ["dark", "light", "system"];

/** The model to send: the saved one only if the provider still offers it,
 *  else null (the provider's default). */
export function resolveModel(saved: string | null, offered: string[] | undefined): string | null {
  return saved && offered?.includes(saved) && saved !== offered[0] ? saved : null;
}

/** Saved settings over the defaults, so settings added later get their
 *  default and nothing invalid survives a reload. */
export function mergeSettings(saved: unknown): Settings {
  const s = (saved && typeof saved === "object" ? saved : {}) as Partial<Settings>;
  return {
    model: typeof s.model === "string" ? s.model : null,
    strictFactual: typeof s.strictFactual === "boolean" ? s.strictFactual : DEFAULT_SETTINGS.strictFactual,
    rememberAnswers: typeof s.rememberAnswers === "boolean" ? s.rememberAnswers : DEFAULT_SETTINGS.rememberAnswers,
    theme: THEMES.includes(s.theme as Theme) ? (s.theme as Theme) : DEFAULT_SETTINGS.theme,
  };
}

export const SETTINGS_KEY = "tailor-settings";

export const DEFAULT_SETTINGS: Settings = {
  model: null,
  strictFactual: false,
  rememberAnswers: true,
  theme: "system",
};

// Storage that never throws (private windows, blocked site data).
const safeStorage = createJSONStorage(() => ({
  getItem: (key: string) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  setItem: (key: string, value: string) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* not saved; the app still works */
    }
  },
  removeItem: (key: string) => {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
}));

export const useApp = create<AppState>()(
  persist(
    (set, get) => ({
      step: "upload",
      reached: 0,
      settings: DEFAULT_SETTINGS,
      run: EMPTY_RUN,
      running: false,
      goTo: (step) => {
        if (stepIndex(step) <= get().reached && !get().running) set({ step });
      },
      advance: (step) => set((s) => ({ step, reached: Math.max(s.reached, stepIndex(step)) })),
      updateRun: (patch) => set((s) => ({ run: { ...s.run, ...patch } })),
      restart: () => set({ step: "upload", reached: 0, run: EMPTY_RUN }),
      updateSettings: (patch) => set((s) => ({ settings: { ...s.settings, ...patch } })),
    }),
    // Only preferences persist; the run itself lives on the server.
    {
      name: SETTINGS_KEY,
      version: 2,
      storage: safeStorage,
      // v2 (redesign): "dark" was the old default, saved for everyone who changed any setting, so it counts as
      // "system" once. The pre-paint script in index.html applies the same rule.
      migrate: (persisted, version) => {
        const settings = (persisted as { settings?: Partial<Settings> } | undefined)?.settings;
        if ((version ?? 0) < 2 && settings?.theme === "dark") return { settings: { ...settings, theme: "system" } };
        return persisted as { settings: Settings };
      },
      partialize: (s) => ({ settings: s.settings }),
      merge: (persisted, current) => ({
        ...current,
        settings: mergeSettings((persisted as { settings?: unknown } | undefined)?.settings),
      }),
    },
  ),
);
