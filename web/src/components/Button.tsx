import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const STYLES: Record<Variant, string> = {
  primary: "bg-pencil text-on-pencil font-semibold shadow-[0_1px_2px_rgb(27_27_31/0.12)] hover:bg-pencil-hover",
  secondary: "border border-field bg-panel text-ink font-medium hover:border-pencil hover:text-pencil",
  ghost: "text-muted underline-offset-4 hover:text-ink hover:underline",
};

export function Button({ variant = "secondary", size = "md", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "md" | "lg" }) {
  const height = size === "lg" ? "h-12 px-6 text-[15px]" : "h-11 px-4.5 text-sm";
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-[4px] transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${height} ${STYLES[variant]} ${className}`}
      {...props}
    />
  );
}
