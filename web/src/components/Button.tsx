import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const STYLES: Record<Variant, string> = {
  primary: "bg-gold text-on-gold font-semibold hover:bg-gold-hover",
  secondary: "border border-line-strong text-ink hover:border-gold",
  ghost: "text-muted hover:text-ink",
};

export function Button({ variant = "secondary", size = "md", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "md" | "lg" }) {
  const height = size === "lg" ? "h-13 px-7 text-[15px]" : "h-11 px-5 text-sm";
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-[2px] tracking-[0.01em] transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${height} ${STYLES[variant]} ${className}`}
      {...props}
    />
  );
}
