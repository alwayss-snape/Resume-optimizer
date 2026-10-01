import { type FocusEvent, useEffect, useId, useRef, useState } from "react";
import type { AppConfig } from "../lib/api";
import { type Theme, resolveModel, useApp } from "../lib/store";
import { Icon } from "./Icon";

const THEMES: { id: Theme; label: string }[] = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "system", label: "System" },
];

function Toggle({ label, help, checked, onChange }: {
  label: string;
  help: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm text-ink">{label}</label>
        <span id={`${id}-help`} className="text-xs leading-relaxed text-muted">{help}</span>
      </div>
      <input id={id} type="checkbox" role="switch" checked={checked} aria-describedby={`${id}-help`}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 size-[22px] shrink-0 cursor-pointer accent-[var(--gold)]" />
    </div>
  );
}

/** The gear menu: model, strict mode, saved answers, theme. A disclosure:
 *  focus moves into it on open; Escape, an outside click or tabbing out
 *  closes it. `config` undefined = still loading, null = server unreachable. */
export function SettingsPopover({ config }: { config: AppConfig | null | undefined }) {
  const [open, setOpen] = useState(false);
  const { settings, updateSettings } = useApp();
  const panel = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const modelId = useId();
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    panel.current?.querySelector<HTMLElement>("select, input")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!panel.current?.contains(target) && !button.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const onBlur = (e: FocusEvent) => {
    const next = e.relatedTarget as Node | null;
    if (next && !panel.current?.contains(next) && !button.current?.contains(next)) setOpen(false);
  };

  const models = config?.models ?? [];
  const model = resolveModel(settings.model, models) ?? models[0] ?? "";

  return (
    <div className="relative" onBlur={onBlur}>
      <button ref={button} type="button" aria-label="Settings" aria-expanded={open} aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className={`flex size-11 items-center justify-center rounded-full border transition-colors ${
          open ? "border-gold text-gold" : "border-line text-muted hover:text-ink"}`}>
        <Icon name="settings" />
      </button>
      {open && (
        <div ref={panel} id={panelId} role="group" aria-label="Settings"
          className="absolute right-0 top-14 z-30 flex w-[min(340px,calc(100vw-32px))] flex-col gap-5 border border-line bg-panel p-5 shadow-[0_24px_60px_rgb(0_0_0/0.35)]">
          <div className="flex flex-col gap-2">
            <label htmlFor={modelId} className="text-[11px] tracking-[0.2em] text-muted">AI MODEL</label>
            <select id={modelId} value={model} disabled={!models.length}
              onChange={(e) => updateSettings({ model: resolveModel(e.target.value, models) })}
              className="h-11 border border-field bg-panel-2 px-3 text-sm text-ink">
              {models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <span className="text-xs text-muted">
              {config ? `Provider: ${config.provider_label}`
                : config === null ? "Can't reach the server, so models can't be listed." : "Loading…"}
            </span>
          </div>
          <Toggle label="Strict factual mode"
            help="If any rewrite fails the fact check, none are used. Off: only the failing ones are dropped."
            checked={settings.strictFactual} onChange={(v) => updateSettings({ strictFactual: v })} />
          <Toggle label="Reuse my answers"
            help="Skills you confirm are offered again for your next job description during this visit. Never shared."
            checked={settings.rememberAnswers} onChange={(v) => updateSettings({ rememberAnswers: v })} />
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-[11px] tracking-[0.2em] text-muted">APPEARANCE</legend>
            <div className="grid grid-cols-3 border border-field">
              {THEMES.map((t) => (
                <label key={t.id}
                  className={`flex h-11 cursor-pointer items-center justify-center border-b-2 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gold ${
                    settings.theme === t.id ? "border-gold bg-gold-soft text-ink" : "border-transparent text-muted hover:text-ink"}`}>
                  <input type="radio" name="theme" value={t.id} checked={settings.theme === t.id}
                    onChange={() => updateSettings({ theme: t.id })} className="sr-only" />
                  {t.label}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );
}
