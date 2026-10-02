import type { AppConfig } from "../lib/api";
import { SettingsPopover } from "./SettingsPopover";
import { Stepper } from "./Stepper";

export function Header({ config }: { config: AppConfig | null | undefined }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-[1240px] items-center justify-between gap-6 px-4 py-3 md:px-8 md:py-4">
        <a href="/" className="flex min-h-11 items-center gap-2 text-ink no-underline">
          <span className="relative font-display text-[24px] font-bold tracking-[-0.02em]">
            Tailores
            {/* an editor's caret under the wordmark */}
            <svg aria-hidden="true" viewBox="0 0 16 8" className="absolute -bottom-2 left-[1.35em] h-2 w-4 text-pencil">
              <path d="M1 7 8 1l7 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="hidden text-[13px] text-muted sm:inline">Resume Studio</span>
        </a>
        <Stepper />
        <SettingsPopover config={config} />
      </div>
    </header>
  );
}
