import { type InputHTMLAttributes, type TextareaHTMLAttributes, useId } from "react";

const BOX = "rounded-[3px] border border-field bg-panel px-3.5 text-[15px] text-ink placeholder:text-muted transition-colors hover:border-ink focus-visible:border-pencil";

export function TextField({ label, className = "", ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId();
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium text-ink">{label}</label>
      <input id={id} className={`h-11 ${BOX}`} {...props} />
    </div>
  );
}

export function TextArea({ label, className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const id = useId();
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium text-ink">{label}</label>
      <textarea id={id} className={`resize-y py-3 leading-relaxed ${BOX}`} {...props} />
    </div>
  );
}
