"""P9.7: AI waits are their own progress event; step lines say "1 bullet" / "10 bullets"."""
from app.analysis.rewriter import _count
from app.api.routes import _progress_event
from app.llm.client import WaitNotice


def test_a_wait_is_its_own_event_with_seconds():
    assert _progress_event(WaitNotice("The free AI service asked us to wait; trying again in 18 s", 18)) == (
        "wait", {"message": "The free AI service asked us to wait; trying again in 18 s", "seconds": 18})
    assert _progress_event("Writing a tailored summary") == ("progress", {"message": "Writing a tailored summary"})


def test_wait_notice_is_still_a_plain_string_for_the_cli():
    notice = WaitNotice("waiting", 5)
    assert notice == "waiting" and f"{notice}" == "waiting" and isinstance(notice, str)


def test_counts_are_pluralised():
    assert _count(1, "bullet") == "1 bullet"
    assert _count(10, "bullet") == "10 bullets"
    assert _count(2, "project bullet") == "2 project bullets"
