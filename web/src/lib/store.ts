import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const STEPS = [
  { id: "upload", label: "Upload" },
  { id: "details", label: "Check details" },
  { id: "review", label: "Review" },
  { id: "results", label: "Results" },
] as const;

export type StepId = (typeof STEPS)[number]["id"];
export type Theme = "dark" | "light" | "system";

export interface Settings {
  model: string | null; // null: the provider's default
  strictFactual: boolean;
  rememberAnswers: boolean;
  theme: Theme;
}

interface AppState {
  step: StepId;
  // Furthest step reached in this run; the stepper lets you go back to any
  // step up to it, never forward past it.
  reached: number;
  settings: Settings;
  goTo: (step: StepId) => void;
  advance: (step: StepId) => void;
  restart: () => void;
  updateSettings: (patch: Partial<Settings>) => void;
}

export const stepIndex = (step: StepId) => STEPS.findIndex((s) => s.id === step);

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
  theme: "dark",
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
      goTo: (step) => {
        if (stepIndex(step) <= get().reached) set({ step });
      },
      advance: (step) => set((s) => ({ step, reached: Math.max(s.reached, stepIndex(step)) })),
      restart: () => set({ step: "upload", reached: 0 }),
      updateSettings: (patch) => set((s) => ({ settings: { ...s.settings, ...patch } })),
    }),
    // Only preferences persist; the run itself lives on the server.
    {
      name: SETTINGS_KEY,
      version: 1,
      storage: safeStorage,
      partialize: (s) => ({ settings: s.settings }),
      merge: (persisted, current) => ({
        ...current,
        settings: mergeSettings((persisted as { settings?: unknown } | undefined)?.settings),
      }),
    },
  ),
);
