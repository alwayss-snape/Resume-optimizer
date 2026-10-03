import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { MAX_UPLOAD_MB, UploadForm, fileProblem } from "./UploadForm";

const file = (name: string, size = 1000) => new File([new Uint8Array(size)], name);

test("fileProblem mirrors the server's checks", () => {
  expect(fileProblem(file("cv.docx"))).toBeNull();
  expect(fileProblem(file("CV.PDF"))).toBeNull();
  expect(fileProblem(file("cv.txt"))).toBeNull(); // plain text is read too (P8.22)
  expect(fileProblem(file("cv.doc"))).toBeNull();
  expect(fileProblem(file("cv.pages"))).toMatch(/\.docx, \.pdf/);
  expect(fileProblem(file("cv.pdf", MAX_UPLOAD_MB * 1024 * 1024 + 1))).toMatch(/larger/);
});

test("submits the file, job description and template once both are given", async () => {
  const user = userEvent.setup({ applyAccept: false });
  const onSubmit = vi.fn();
  render(<UploadForm intent="tailor" onSubmit={onSubmit} />);
  const submit = screen.getByRole("button", { name: /Read my resume/ });
  const anyFile = userEvent.setup({ applyAccept: false }); // the form checks the type itself

  await user.click(submit);
  expect(screen.getByRole("alert")).toHaveTextContent("Add your resume first, or paste it as text.");

  await anyFile.upload(screen.getByLabelText(/Drop your resume here/), file("notes.pages"));
  expect(screen.getByRole("alert")).toHaveTextContent(/\.docx, \.pdf/);

  await user.upload(screen.getByLabelText(/Drop your resume here/), file("cv.docx"));
  await user.click(screen.getByRole("radio", { name: /Keep my layout/ }));
  await user.click(submit);
  expect(screen.getByRole("alert")).toHaveTextContent("Paste the job description.");

  await user.type(screen.getByLabelText("The job description"), "Senior Data Scientist");
  await user.click(submit);
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ jdText: "Senior Data Scientist", template: "keep" }));
  expect(onSubmit.mock.calls[0][0].file.name).toBe("cv.docx");
});

test("a PDF can't keep its layout, and replaces an earlier 'keep' choice", async () => {
  const user = userEvent.setup();
  render(<UploadForm intent="tailor" onSubmit={vi.fn()} />);
  await user.upload(screen.getByLabelText(/Drop your resume here/), file("cv.docx"));
  await user.click(screen.getByRole("radio", { name: /Keep my layout/ }));
  await user.upload(screen.getByLabelText(/Drop your resume here/), file("cv.pdf"));
  expect(screen.getByRole("radio", { name: /Keep my layout/ })).toBeDisabled();
  expect(screen.getByRole("radio", { name: /^ATS template/ })).toBeChecked();
});

test("drag and drop: one file is taken, several are refused, and the error marks the field", async () => {
  const onSubmit = vi.fn();
  render(<UploadForm intent="check" onSubmit={onSubmit} />);
  const zone = screen.getByText("Drop your resume here").closest("label")!;
  fireEvent.drop(zone, { dataTransfer: { files: [file("a.pdf"), file("b.pdf")], types: ["Files"] } });
  expect(screen.getByRole("alert")).toHaveTextContent("one file");
  expect(screen.getByLabelText(/Drop your resume here/)).toHaveAttribute("aria-invalid", "true");

  fireEvent.drop(zone, { dataTransfer: { files: [file("cv.pdf")], types: ["Files"] } });
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("cv.pdf")).toBeInTheDocument();
});

test("a missing job description focuses the box", async () => {
  const user = userEvent.setup();
  render(<UploadForm intent="check" onSubmit={vi.fn()} />);
  await user.upload(screen.getByLabelText(/Drop your resume here/), file("cv.docx"));
  await user.click(screen.getByRole("button", { name: /Check my match/ }));
  expect(screen.getByLabelText("The job description")).toHaveFocus();
  expect(screen.getByLabelText("The job description")).toHaveAccessibleDescription("Error: Paste the job description.");
});

test("the match check needs no output format", () => {
  render(<UploadForm intent="check" onSubmit={vi.fn()} />);
  expect(screen.queryByText("Output format")).toBeNull();
  expect(screen.getByRole("button", { name: /Check my match/ })).toBeInTheDocument();
});


test("pasted text is sent as a plain-text resume with the ATS template", async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  render(<UploadForm intent="tailor" onSubmit={onSubmit} />);
  await user.click(screen.getByText("No file? Paste your resume as text"));
  await user.type(screen.getByLabelText("Your resume as text"), "Jane Doe\njane@example.com");
  await user.type(screen.getByLabelText("The job description"), "Data analyst with SQL");
  await user.click(screen.getByRole("button", { name: /Read my resume/ }));
  const values = onSubmit.mock.calls[0][0];
  expect(values.file.name).toBe("resume.txt");
  expect(values.template).toBe("ats");
});
