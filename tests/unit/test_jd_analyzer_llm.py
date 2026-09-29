from app.analysis.jd_analyzer import JDAnalyzer
from app.llm.schemas import JDRequirementSelection


class _FakeLLMClient:
    """Minimal duck-typed stand-in for LLMClient — JDAnalyzer only calls
    is_available() and generate_json() on it, so no real network/Groq/Ollama
    call is needed to test the selection logic."""

    def __init__(self, available=True, selection=None, raise_error=False):
        self._available = available
        self._selection = selection if selection is not None else []
        self._raise_error = raise_error
        self.calls = []

    def is_available(self):
        return self._available

    def generate_json(self, messages, schema_model, **kwargs):
        self.calls.append(messages)
        if self._raise_error:
            raise RuntimeError("simulated LLM failure")
        return JDRequirementSelection(requirement_line_indices=self._selection)


def test_reflow_merges_hard_wrapped_bullet_before_scoring():
    """A bullet wrapped mid-sentence across two physical lines (common when
    a JD is copy-pasted from a job board at a fixed column width) must be
    rejoined into ONE line before scoring — otherwise the wrapped remainder
    ("large scale, including Kafka and gRPC.") is scored as an isolated,
    context-free fragment on its own. (Whether the rejoined line then gets
    further segmented on internal "and"s is separate, pre-existing
    behavior in _segment_line, not what this test checks.)"""
    jd_text = (
        "Requirements:\n"
        "- Experience with distributed systems at\n"
        "  large scale, including Kafka.\n"
        "- 5+ years of experience with Python.\n"
    )
    lines = JDAnalyzer()._reflow_lines(jd_text)
    assert "- Experience with distributed systems at large scale, including Kafka." in lines
    assert not any(l.strip() == "large scale, including Kafka." for l in lines)


def test_reflow_does_not_merge_metadata_or_heading_lines():
    """Short label lines like 'Job Title:' / 'Company:' must never get
    merged into the following line just because they don't end in
    punctuation — this was a real regression risk with a naive reflow."""
    jd_text = "Job Title: Senior Backend Engineer\nCompany: CloudScale Inc.\n\nRequirements:\n- Python.\n"
    jd = JDAnalyzer(llm_client=None).analyze(jd_text)
    assert jd.job_title == "Senior Backend Engineer"
    assert jd.company == "CloudScale Inc."


def test_llm_selection_excludes_boilerplate_bullet_the_heuristic_would_keep():
    """Core fix: a bulleted perks/benefits line ('flexible PTO and remote
    work') would pass the deterministic heuristic just for being a bullet.
    When an LLM is available, its selection is authoritative, so it can
    correctly exclude this line while keeping the real requirement."""
    jd_text = (
        "Requirements:\n"
        "- 5+ years of experience with Python.\n"
        "Benefits:\n"
        "- Flexible PTO and remote work options.\n"
        "- Competitive salary and equity.\n"
    )
    lines = JDAnalyzer()._reflow_lines(jd_text)
    # The Python requirement is the only genuine requirement line; find its index.
    python_idx = next(i for i, l in enumerate(lines) if "Python" in l)

    fake_client = _FakeLLMClient(available=True, selection=[python_idx])
    jd = JDAnalyzer(llm_client=fake_client).analyze(jd_text)

    texts = [r.text for r in jd.requirements]
    assert any("Python" in t for t in texts)
    assert not any("Flexible PTO" in t for t in texts)
    assert not any("Competitive salary" in t for t in texts)
    assert len(fake_client.calls) == 1  # LLM was actually consulted


def test_llm_unavailable_falls_back_to_heuristic():
    jd_text = "Requirements:\n- 5+ years of experience with Python.\n"
    fake_client = _FakeLLMClient(available=False)
    jd = JDAnalyzer(llm_client=fake_client).analyze(jd_text)
    texts = [r.text for r in jd.requirements]
    assert any("Python" in t for t in texts)


def test_llm_error_falls_back_to_heuristic():
    jd_text = "Requirements:\n- 5+ years of experience with Python.\n"
    fake_client = _FakeLLMClient(available=True, raise_error=True)
    jd = JDAnalyzer(llm_client=fake_client).analyze(jd_text)
    texts = [r.text for r in jd.requirements]
    assert any("Python" in t for t in texts)


def test_degenerate_empty_llm_selection_falls_back_to_heuristic():
    """An empty selection over a non-trivial candidate pool looks like a
    bad/degenerate LLM response, not a JD with zero requirements — fall
    back rather than silently returning nothing."""
    jd_text = (
        "Requirements:\n"
        "- 5+ years of experience with Python.\n"
        "- Experience with SQL.\n"
        "- Experience with distributed systems.\n"
    )
    fake_client = _FakeLLMClient(available=True, selection=[])
    jd = JDAnalyzer(llm_client=fake_client).analyze(jd_text)
    texts = [r.text for r in jd.requirements]
    assert any("Python" in t for t in texts)


def test_llm_hallucinated_index_out_of_range_is_ignored():
    jd_text = "Requirements:\n- 5+ years of experience with Python.\n- Experience with SQL.\n"
    lines = JDAnalyzer()._reflow_lines(jd_text)
    python_idx = next(i for i, l in enumerate(lines) if "Python" in l)
    # 999 is a hallucinated index the analyzer never sent the model.
    fake_client = _FakeLLMClient(available=True, selection=[python_idx, 999])
    jd = JDAnalyzer(llm_client=fake_client).analyze(jd_text)
    texts = [r.text for r in jd.requirements]
    assert any("Python" in t for t in texts)
    assert not any("SQL" in t for t in texts)  # not selected, so excluded
