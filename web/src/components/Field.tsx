import { type InputHTMLAttributes, type TextareaHTMLAttributes, useId } from "react";

const BOX = "border border-field bg-panel-2 px-3.5 text-sm text-ink placeholder:text-muted";

export function TextField({ label, className = "", ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId();
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-[13px] text-muted">{label}</label>
      <input id={id} className={`h-11 ${BOX}`} {...props} />
    </div>
  );
}

export function TextArea({ label, className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const id = useId();
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-[13px] text-muted">{label}</label>
      <textarea id={id} className={`resize-y py-3 leading-relaxed ${BOX}`} {...props} />
    </div>
  );
}
