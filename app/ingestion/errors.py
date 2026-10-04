"""A file the tool can't read, with a message the person can act on (P8.22).

A damaged .docx or a password-protected PDF used to end in "Something went
wrong on our side" (an unhandled 500), and a scanned PDF parsed as empty.
"""


class UnreadableFile(ValueError):
    """`str(error)` is the user-facing explanation."""


DAMAGED_DOCX = ("This Word file looks damaged or isn't a real .docx. Open it in Word, save it again as .docx, "
                "and upload that (or upload a PDF saved from it).")
LOCKED_PDF = ("This PDF is password-protected, so its text can't be read. Save a copy without the password "
              "(or print it to a new PDF) and upload that.")
DAMAGED_PDF = "This PDF can't be opened; it may be damaged. Save it again from the original and upload that."
SCANNED_PDF = ("This PDF looks like a scanned image: there's no text in it to read. Upload the original Word "
               "file, or a PDF saved from it rather than scanned.")
NO_TEXT = "There's no text in this file to read. Check it's the right file."
CONVERT_FAILED = ("This file couldn't be converted for reading. Save it as .docx or PDF in your word processor "
                  "and upload that.")
DAMAGED_FILE = ("This file looks damaged: it's mostly unreadable characters. Save it again from the original "
                "(as .docx or PDF if you can) and upload that.")
EMPTY_FILE = "This file is empty. Check it's the right file, or paste your resume as text."
