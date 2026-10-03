import { type DragEvent, useEffect, useId, useRef, useState } from "react";
import type { Intent, Template } from "../lib/store";
import { Button } from "./Button";
import { Icon } from "./Icon";

export type { Intent, Template };

export interface UploadValues {
  file: File;
  jdText: string;
  template: Template;
}

export const MAX_UPLOAD_MB = 5; // until /api/config says otherwise
// .doc / .odt / .rtf are converted to .docx on the server; .txt is read as plain text (P8.22).
const ACCEPTED = [".docx", ".pdf", ".doc", ".odt", ".rtf", ".txt"];
const NO_LAYOUT = [".pdf", ".txt"]; // nothing to keep the layout of

const extension = (name: string) => name.slice(name.lastIndexOf(".")).toLowerCase();
const formatSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

/** Why a file can't be used, or null. Mirrors the server's checks. */
export function fileProblem(file: File, maxMb = MAX_UPLOAD_MB): string | null {
  if (!ACCEPTED.includes(extension(file.name))) return "Please choose a .docx, .pdf, .doc, .odt, .rtf or .txt file.";
  if (file.size > maxMb * 1024 * 1024) return `The file is larger than ${maxMb} MB.`;
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
    <label className={`relative flex items-center gap-5 rounded-[3px] bg-panel p-5 shadow-sheet transition-[border-color,box-shadow] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-3 has-[:focus-visible]:outline-pencil ${
      disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"} ${selected ? "border-2 border-pencil p-[19px]" : "border border-field hover:border-ink"}`}>
      <input type="radio" name="template" value={value} checked={selected} disabled={disabled}
        onChange={() => onSelect(value)} className="sr-only" />
      {children}
      <span className="flex flex-col gap-2">
        <span className="flex flex-wrap items-center gap-2.5">
          <span className="font-display text-lg font-bold tracking-[-0.01em]">{title}</span>
          {badge && <span className="rounded-[3px] bg-pencil-soft px-2 py-0.5 text-xs font-semibold text-pencil">{badge}</span>}
        </span>
        <span className="text-sm leading-relaxed text-muted">{text}</span>
      </span>
      {selected && (
        <span aria-hidden="true" className="absolute right-3 top-3 flex size-6 items-center justify-center rounded-full bg-pencil text-on-pencil">
          <Icon name="check" size={14} strokeWidth={2.4} />
        </span>
      )}
    </label>
  );
}

/** Resume + job description + output format. Validates locally; the
 *  parent decides what submitting does. */
export function UploadForm({ intent, onSubmit, busy = false, initial, maxUploadMb = MAX_UPLOAD_MB, serverError, serverErrorKey }: {
  intent: Intent;
  onSubmit: (values: UploadValues) => void;
  busy?: boolean;
  initial?: { file: File | null; jdText: string; template: Template };
  maxUploadMb?: number;
  serverError?: string | null;
  serverErrorKey?: number; // changes per failure, so a repeated message is announced again
}) {
  const [file, setFile] = useState<File | null>(initial?.file ?? null);
  const [pasteText, setPasteText] = useState("");
  const [jdText, setJdText] = useState(initial?.jdText ?? "");
  const [template, setTemplate] = useState<Template>(initial?.template ?? "ats");
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
    const problem = files.length > 1 ? "Please add one file: your resume." : fileProblem(picked, maxUploadMb);
    if (problem) return fail(problem, "file");
    setError(null);
    setFile(picked);
    if (NO_LAYOUT.includes(extension(picked.name))) setTemplate("ats"); // a PDF or text can't keep its layout
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    choose(e.dataTransfer.files);
  };

  const submit = () => {
    const pasted = pasteText.trim();
    if (!file && pasted) {
      // Pasted text goes up as a plain-text file; the server reads it like any upload (P8.22).
      if (!jdText.trim()) return fail("Paste the job description.", "jd");
      setError(null);
      return onSubmit({ file: new File([pasted], "resume.txt", { type: "text/plain" }), jdText, template: "ats" });
    }
    if (!file) return fail("Add your resume first, or paste it as text.", "file");
    if (!jdText.trim()) return fail("Paste the job description.", "jd");
    setError(null);
    onSubmit({ file, jdText, template });
  };

  const invalid = (field: "file" | "jd") =>
    error?.field === field ? { "aria-invalid": true, "aria-describedby": errorId } : {};

  const isPdf = file ? NO_LAYOUT.includes(extension(file.name)) : pasteText.trim().length > 0;

  return (
    <form className="flex flex-col gap-10" onSubmit={(e) => { e.preventDefault(); submit(); }} noValidate>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="sheet flex flex-col gap-4 rounded-[3px] p-6 md:p-7">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="font-display text-[22px] font-bold tracking-[-0.015em]">Your resume</h2>
            <span className="text-[13px] text-muted">DOCX, PDF, DOC, ODT, RTF or TXT, up to {maxUploadMb} MB</span>
          </div>
          <label htmlFor={fileId}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false);
            }}
            onDrop={onDrop}
            className={`flex flex-1 cursor-pointer flex-col items-center justify-center gap-3 rounded-[3px] border-2 border-dashed px-6 py-10 text-center transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-3 has-[:focus-visible]:outline-pencil ${
              dragging ? "border-pencil bg-pencil-soft" : "border-field hover:border-pencil hover:bg-pencil-soft has-[[aria-invalid=true]]:border-danger"}`}>
            <Icon name="upload" size={32} strokeWidth={1.5} className="text-pencil" />
            <span className="text-base font-semibold">Drop your resume here</span>
            <span className="text-sm text-muted">or <span className="font-medium text-pencil underline">browse files</span></span>
            <input id={fileId} ref={input} type="file" accept={ACCEPTED.join(",")} className="sr-only"
              {...invalid("file")}
              onChange={(e) => {
                choose(e.target.files);
                e.target.value = ""; // so picking the same file again still counts
              }} />
          </label>
          {file && (
            <div className="flex items-center gap-3.5 rounded-[3px] border border-success-line bg-panel-2 px-4 py-3">
              <Icon name="check" className="text-success" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-medium">{file.name}</span>
                <span className="text-xs text-muted">{formatSize(file.size)}</span>
              </span>
              <button type="button" onClick={() => input.current?.click()}
                className="min-h-11 text-sm font-medium text-pencil underline-offset-4 hover:underline">Replace</button>
            </div>
          )}
          {!file && (
            <details className="group">
              <summary className="flex min-h-11 w-fit cursor-pointer list-none items-center gap-2 text-sm font-medium text-pencil [&::-webkit-details-marker]:hidden">
                <Icon name="arrow-right" size={14} strokeWidth={2} className="transition-transform group-open:rotate-90" />
                No file? Paste your resume as text
              </summary>
              <label htmlFor={`${fileId}-paste`} className="sr-only">Your resume as text</label>
              <textarea id={`${fileId}-paste`} value={pasteText} onChange={(e) => setPasteText(e.target.value)} rows={8}
                placeholder="Paste your resume: name and contact first, then each section."
                className="mt-2 w-full resize-y rounded-[3px] border border-field bg-panel p-3.5 text-[15px] leading-relaxed text-ink placeholder:text-muted hover:border-ink focus-visible:border-pencil" />
            </details>
          )}
        </section>

        <section className="sheet flex flex-col gap-4 rounded-[3px] p-6 md:p-7">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="font-display text-[22px] font-bold tracking-[-0.015em]"><label htmlFor={jdId}>The job description</label></h2>
            <span className="text-[13px] text-muted">Paste the full text</span>
          </div>
          <textarea id={jdId} ref={jd} value={jdText} onChange={(e) => setJdText(e.target.value)} {...invalid("jd")}
            placeholder="Paste the job title, responsibilities and requirements here."
            className="min-h-[232px] flex-1 resize-y rounded-[3px] border border-field bg-panel p-4 text-[15px] leading-relaxed text-ink placeholder:text-muted hover:border-ink focus-visible:border-pencil aria-[invalid=true]:border-2 aria-[invalid=true]:border-danger" />
          <span className="tabular self-end text-[13px] text-muted">{jdText.length.toLocaleString()} characters</span>
        </section>
      </div>

      {intent === "tailor" && (
        <fieldset className="flex flex-col gap-4">
          <legend className="mb-4 font-display text-lg font-bold tracking-[-0.01em]">Output format</legend>
          <div className="grid gap-6 md:grid-cols-2">
            <TemplateCard value="ats" current={template} onSelect={setTemplate} title="ATS template" badge="Recommended"
              text="Clean single-column A4 layout. Sections are ordered for the role and fitted to one or two pages.">
              <span aria-hidden="true" className="flex h-[120px] w-[92px] shrink-0 flex-col gap-[5px] border border-line bg-paper p-2.5 shadow-sheet">
                <span className="h-1.5 w-3/5 bg-[#1b1b1f]" />
                <span className="h-[3px] w-4/5 bg-[#9a9ba2]" />
                <span className="my-0.5 h-px bg-[#2f62d8]" />
                {[95, 88, 92, 40, 90, 70].map((w, i) => (
                  <span key={i} className={`h-[3px] ${i === 3 ? "bg-[#1b1b1f]" : "bg-[#c9c9c3]"}`} style={{ width: `${w}%` }} />
                ))}
              </span>
            </TemplateCard>
            <TemplateCard value="keep" current={template} onSelect={setTemplate} title="Keep my layout" disabled={isPdf}
              text={isPdf ? "Only for Word uploads. PDFs and text always use the ATS template."
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
        <Button type="submit" variant="primary" size="lg" disabled={busy} aria-busy={busy}>
          {busy ? (intent === "tailor" ? "Reading your resume…" : "Checking your match…")
            : intent === "tailor" ? "Read my resume" : "Check my match"}
          {!busy && <Icon name="arrow-right" />}
        </Button>
        <div>
          {error ? <p key={error.n} id={errorId} role="alert" className="flex items-center gap-2 text-sm font-medium text-danger"><Icon name="alert" size={16} /><span><span className="font-semibold">Error:</span> {error.text}</span></p>
            : serverError && <p key={serverErrorKey} role="alert" className="flex items-center gap-2 text-sm font-medium text-danger"><Icon name="alert" size={16} /><span><span className="font-semibold">Error:</span> {serverError}</span></p>}
        </div>
      </div>
    </form>
  );
}
