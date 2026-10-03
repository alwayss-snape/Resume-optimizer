import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { PrivacyNote } from "./Landing";

test("says where the resume goes and when files are deleted", () => {
  const { rerender } = render(<PrivacyNote config={{ provider: "groq", provider_label: "Groq (cloud)", models: [],
    max_upload_mb: 5, cloud: true, session_minutes: 60 }} />);
  expect(screen.getByText(/sent to Groq \(cloud\), a cloud AI service/)).toBeInTheDocument();
  expect(screen.getByText(/after 60 minutes/)).toBeInTheDocument();
  rerender(<PrivacyNote config={{ provider: "ollama", provider_label: "Ollama (local)", models: [], max_upload_mb: 5,
    cloud: false, session_minutes: 30 }} />);
  expect(screen.getByText(/nothing is sent to an outside AI service/)).toBeInTheDocument();
});
