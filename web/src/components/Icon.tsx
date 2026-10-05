// Inline stroke icons, drawn to match the thin-line look.
type Name = "check" | "settings" | "upload" | "file" | "close" | "arrow-right" | "alert" | "clock";

const PATHS: Record<Name, string[]> = {
  check: ["M20 6 9 17l-5-5"],
  settings: ["M4 7h10M18 7h2M4 17h4M12 17h8", "M16 5a2 2 0 1 1 0 4 2 2 0 0 1 0-4z", "M10 15a2 2 0 1 1 0 4 2 2 0 0 1 0-4z"],
  upload: ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5", "M12 17v-6", "M9.5 13.5 12 11l2.5 2.5"],
  file: ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5"],
  close: ["M18 6 6 18M6 6l12 12"],
  "arrow-right": ["M4 12h15M13 6l6 6-6 6"],
  alert: ["M12 3 2.5 20h19z", "M12 10v4.5", "M12 17.2v.3"],
  clock: ["M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z", "M12 7.5V12l3 2"],
};

export function Icon({ name, size = 18, strokeWidth = 1.6, className }: {
  name: Name;
  size?: number;
  strokeWidth?: number;
  className?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
