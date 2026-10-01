import { type DragEvent, useEffect, useId, useRef, useState } from "react";
import { Button } from "./Button";
import { Icon } from "./Icon";

export type Intent = "tailor" | "check";
export type Template = "ats" | "keep";

export interface UploadValues {
  file: File;
  jdText: string;
  template: Template;
}

export const MAX_UPLOAD_MB = 5;
const ACCEPTED = [".docx", ".pdf"];

const extension = (name: string) => name.slice(name.lastIndexOf(".")).toLowerCase();
const formatSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

/** Why a file can't be used, or null. Mirrors the server's checks. */
export function fileProblem(file: File): string | null {
  if (!ACCEPTED.includes(extension(file.name))) return "Please choose a .docx or .pdf file.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `The file is larger than ${MAX_UPLOAD_MB} MB.`;
  return null;
}

function TemplateCard({ value, current, onSelect, title, badge, text, disabled, children }: {
  value: Template;
  current: Template;
  onSelect: (t: Template) => void;
  title: string;
  badge?: string;
  text: string;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  const selected = current === value;
  return (
    <label className={`flex items-center gap-5 border bg-panel p-5 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gold ${
      disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"} ${selected ? "border-gold" : "border-line hover:border-line-strong"}`}>
      <input type="radio" name="template" value={value} checked={selected} disabled={disabled}
        onChange={() => onSelect(value)} className="sr-only" />
      {children}
      <span className="flex flex-col gap-2">
        <span className="flex flex-wrap items-center gap-2.5">
          <span className="font-display text-[22px] font-semibold">{title}</span>
          {badge && <span className="bg-gold px-2 py-0.5 text-[11px] tracking-[0.12em] text-on-gold">{badge}</span>}
        </span>
        <span className="text-sm leading-relaxed text-muted">{text}</span>
      </span>
    </label>
  );
}

/** Resume + job description + output format. Validates locally; the
 *  parent decides what submitting does. */
export function UploadForm({ intent, onSubmit, busy = false }: {
  intent: Intent;
  onSubmit: (values: UploadValues) => void;
  busy?: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [template, setTemplate] = useState<Template>("ats");
  const [dragging, setDragging] = useState(false);
  // field: which input the message is about, so it can be marked invalid
  // and focused; n: re-mounts the alert so a repeated message is announced.
  const [error, setError] = useState<{ text: string; field: "file" | "jd"; n: number } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const jd = useRef<HTMLTextAreaElement>(null);
  const jdId = useId();
  const fileId = useId();
  const errorId = useId();

  // A file dropped beside the drop zone would make the browser open it and
  // leave the app.
  useEffect(() => {
    const block = (e: globalThis.DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) e.preventDefault();
    };
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  const fail = (text: string, field: "file" | "jd") => {
    setError((e) => ({ text, field, n: (e?.n ?? 0) + 1 }));
    (field === "file" ? input : jd).current?.focus();
  };

  const choose = (files: FileList | null | undefined) => {
    const picked = files?.[0];
    if (!picked) return;
    const problem = files.length > 1 ? "Please add one file: your resume." : fileProblem(picked);
    if (problem) return fail(problem, "file");
    setError(null);
    setFile(picked);
    if (extension(picked.name) === ".pdf") setTemplate("ats"); // a PDF can't keep its layout
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    choose(e.dataTransfer.files);
  };

  const submit = () => {
    if (!file) return fail("Add your resume first.", "file");
    if (!jdText.trim()) return fail("Paste the job description.", "jd");
    setError(null);
    onSubmit({ file, jdText, template });
  };

  const invalid = (field: "file" | "jd") =>
    error?.field === field ? { "aria-invalid": true, "aria-describedby": errorId } : {};

  const isPdf = file ? extension(file.name) === ".pdf" : false;

  return (
    <form className="flex flex-col gap-10" onSubmit={(e) => { e.preventDefault(); submit(); }} noValidate>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="flex flex-col gap-4 border border-line bg-panel p-6 md:p-7">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="font-display text-[26px] font-semibold">Your resume</h2>
            <span className="text-xs text-muted">DOCX or PDF, up to {MAX_UPLOAD_MB} MB</span>
          </div>
          <label htmlFor={fileId}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false);
            }}
            onDrop={onDrop}
            className={`flex cursor-pointer flex-col items-center gap-3 border border-dashed px-6 py-9 text-center transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gold ${
              dragging ? "border-gold bg-gold-soft" : "border-field hover:border-gold"}`}>
            <Icon name="upload" size={34} strokeWidth={1.3} className="text-gold" />
            <span className="text-base">Drop your resume here</span>
            <span className="text-[13px] text-muted">or <span className="text-gold underline">browse files</span></span>
            <input id={fileId} ref={input} type="file" accept={ACCEPTED.join(",")} className="sr-only"
              {...invalid("file")}
              onChange={(e) => {
                choose(e.target.files);
                e.target.value = ""; // so picking the same file again still counts
              }} />
          </label>
          {file && (
            <div className="flex items-center gap-3.5 border border-line bg-panel-2 px-4 py-3">
              <Icon name="check" className="text-success" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm">{file.name}</span>
                <span className="text-xs text-muted">{formatSize(file.size)}</span>
              </span>
              <button type="button" onClick={() => input.current?.click()}
                className="min-h-11 text-[13px] text-muted hover:text-ink">Replace</button>
            </div>
          )}
        </section>

        <section className="flex flex-col gap-4 border border-line bg-panel p-6 md:p-7">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="font-display text-[26px] font-semibold"><label htmlFor={jdId}>The job description</label></h2>
            <span className="text-xs text-muted">Paste the full text</span>
          </div>
          <textarea id={jdId} ref={jd} value={jdText} onChange={(e) => setJdText(e.target.value)} {...invalid("jd")}
            placeholder="Paste the job title, responsibilities and requirements here."
            className="min-h-[232px] flex-1 resize-y border border-field bg-panel-2 p-4 text-sm leading-relaxed text-ink placeholder:text-muted" />
          <span className="self-end text-xs text-muted">{jdText.length.toLocaleString()} characters</span>
        </section>
      </div>

      {intent === "tailor" && (
        <fieldset className="flex flex-col gap-4">
          <legend className="mb-4 text-xs tracking-[0.24em] text-muted">OUTPUT FORMAT</legend>
          <div className="grid gap-6 md:grid-cols-2">
            <TemplateCard value="ats" current={template} onSelect={setTemplate} title="ATS template" badge="RECOMMENDED"
              text="Clean single-column A4 layout. Sections are ordered for the role and fitted to one or two pages.">
              <span aria-hidden="true" className="flex h-[120px] w-[92px] shrink-0 flex-col gap-[5px] bg-paper p-2.5">
                <span className="h-1.5 w-3/5 bg-[#1a1a17]" />
                <span className="h-[3px] w-4/5 bg-[#8c8678]" />
                <span className="my-0.5 h-px bg-gold" />
                {[95, 88, 92, 40, 90, 70].map((w, i) => (
                  <span key={i} className={`h-[3px] ${i === 3 ? "bg-[#1a1a17]" : "bg-[#8c8678]"}`} style={{ width: `${w}%` }} />
                ))}
              </span>
            </TemplateCard>
            <TemplateCard value="keep" current={template} onSelect={setTemplate} title="Keep my layout" disabled={isPdf}
              text={isPdf ? "Only for .docx uploads. PDFs always use the ATS template."
                : "Rewrites go into your own DOCX design. Order and page length stay as they are."}>
              <span aria-hidden="true" className="flex h-[120px] w-[92px] shrink-0 gap-1.5 bg-line p-2.5">
                <span className="w-[26px] bg-line-strong" />
                <span className="flex flex-1 flex-col gap-[5px]">
                  {[80, 100, 85, 100, 70].map((w, i) => (
                    <span key={i} className="h-[3px] bg-line-strong" style={{ width: `${w}%` }} />
                  ))}
                </span>
              </span>
            </TemplateCard>
          </div>
        </fieldset>
      )}

      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
        <Button type="submit" variant="primary" size="lg" disabled={busy}>
          {intent === "tailor" ? "Read my resume" : "Check my match"}
          <Icon name="arrow-right" />
        </Button>
        <div>
          {error && <p key={error.n} id={errorId} role="alert" className="text-sm text-danger">{error.text}</p>}
        </div>
      </div>
    </form>
  );
}
