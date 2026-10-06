import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import update_docs  # noqa: E402


def test_change_log_round_trip_keeps_one_separator_per_entry():
    """Each commit re-read the log with the "---" after every entry kept, then
    joined with another: the separators grew by one per entry per commit
    (7,000+ by P9.22)."""
    head = "# Log\n<!-- entries below; newest first -->\n"
    entries = [("b", "<!-- entry:b -->\n## B\n"), ("a", "<!-- entry:a -->\n## A\n")]
    text = update_docs._join(head, entries)
    for _ in range(3):
        text = update_docs._join(*update_docs._split_entries(text))
    assert text.count("\n---\n") == 1
    assert "## A" in text and "## B" in text
