import type { AppConfig } from "../lib/api";
import { SettingsPopover } from "./SettingsPopover";
import { Stepper } from "./Stepper";

export function Header({ config }: { config: AppConfig | null | undefined }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-[1240px] items-center justify-between gap-6 px-4 py-4 md:px-8 md:py-5">
        <a href="/" className="flex items-baseline gap-2.5 text-ink no-underline">
          <span className="font-display text-[28px] font-semibold tracking-[0.02em]">Tailor</span>
          <span className="hidden text-[11px] tracking-[0.22em] text-muted sm:inline">RESUME STUDIO</span>
        </a>
        <Stepper />
        <SettingsPopover config={config} />
      </div>
    </header>
  );
}
