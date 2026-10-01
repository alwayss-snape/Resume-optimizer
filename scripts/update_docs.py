#!/usr/bin/env python3
"""Regenerate the repo's living docs: the knowledge graph and the change log.

Stdlib only and fully deterministic (no LLM), so it is safe to run from git
hooks on every commit.

    python scripts/update_docs.py graph              # write docs/KNOWLEDGE_GRAPH.{json,md}
    python scripts/update_docs.py graph --check      # exit 1 if they are out of date
    python scripts/update_docs.py log-entry [REV]    # add/replace the CHANGE_LOG entry for REV (default HEAD)
    python scripts/update_docs.py is-major [REV]     # exit 0 if REV deserves a CHANGE_LOG entry
    python scripts/update_docs.py backfill [--force] # rebuild CHANGE_LOG from full git history

See docs/KNOWLEDGE_GRAPH.md for what the graph contains and .githooks/ for
how this is wired into commits.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(ROOT, "docs")
GRAPH_JSON = os.path.join(DOCS_DIR, "KNOWLEDGE_GRAPH.json")
GRAPH_MD = os.path.join(DOCS_DIR, "KNOWLEDGE_GRAPH.md")
CHANGE_LOG = os.path.join(DOCS_DIR, "CHANGE_LOG.md")

# Folders/files that make up the project map. Everything else (virtualenvs,
# run outputs, fixtures' binary content) is ignored.
SCAN_PREFIXES = ("app/", "scripts/", "tests/", ".githooks/")
ROOT_FILES = ("pyproject.toml", ".env.example", "README.md", "ARCHITECTURE.md", "BUILD.md", "CLAUDE.md", "ollama.py")

# A commit gets a CHANGE_LOG entry only if it touches one of these.
MAJOR_PREFIXES = ("app/", "scripts/", "tests/", ".githooks/", "pyproject.toml")
SKIP_LOG_MARKER = "[skip log]"

# Y axis of the matrix: which architectural layer a file belongs to.
LAYERS = [
    ("app/ingestion/", "Ingestion"),
    ("app/analysis/", "Analysis"),
    ("app/llm/", "LLM"),
    ("app/validation/", "Validation"),
    ("app/rendering/", "Rendering"),
    ("app/domain/", "Domain models"),
    ("app/services/", "Services"),
    ("app/config/", "Config"),
    ("app/api/", "Web API"),
    ("app/ui.py", "Entry points"),
    ("app/cli.py", "Entry points"),
    ("tests/", "Tests"),
    ("scripts/", "Tooling"),
    (".githooks/", "Tooling"),
    ("docs/", "Docs"),
]
GENERATED_DOCS = ("docs/KNOWLEDGE_GRAPH.json", "docs/KNOWLEDGE_GRAPH.md", "docs/CHANGE_LOG.md")

# Z axis of the matrix: which pipeline stage(s) a file serves. Hand-maintained
# on purpose -- stage membership is a design fact, not something the AST can
# infer. New app/ files that are missing here show up as "Unmapped" in the
# generated doc, so gaps are visible instead of silent.
STAGES = [
    "1 Ingest", "2 Normalize", "3 JD analysis", "4 Match", "5 Score",
    "6 Plan", "7 Rewrite", "8 Validate", "9 Render", "10 Report",
]
STAGE_MAP: Dict[str, List[str]] = {
    "app/ingestion/docx.py": ["1 Ingest"],
    "app/ingestion/pdf.py": ["1 Ingest"],
    "app/ingestion/ocr.py": ["1 Ingest"],
    "app/analysis/resume_normalizer.py": ["2 Normalize"],
    "app/analysis/structure_extractor.py": ["2 Normalize"],
    "app/domain/resume.py": ["2 Normalize"],
    "app/domain/resume_document.py": ["2 Normalize", "9 Render"],
    "app/domain/evidence.py": ["2 Normalize", "4 Match"],
    "app/analysis/jd_analyzer.py": ["3 JD analysis"],
    "app/domain/job.py": ["3 JD analysis"],
    "app/validation/safety.py": ["3 JD analysis"],
    "app/analysis/matcher.py": ["4 Match"],
    "app/analysis/semantic_matcher.py": ["4 Match"],
    "app/analysis/terminology.py": ["4 Match"],
    "app/domain/report.py": ["4 Match", "5 Score"],
    "app/analysis/scoring.py": ["5 Score"],
    "app/analysis/summary_writer.py": ["7 Rewrite"],
    "app/analysis/skills_tailor.py": ["7 Rewrite"],
    "app/analysis/gap_questions.py": ["6 Plan"],
    "app/analysis/experience.py": ["2 Normalize", "7 Rewrite"],
    "app/analysis/keyword_match.py": ["5 Score"],
    "app/analysis/tailor_planner.py": ["6 Plan"],
    "app/domain/tailoring.py": ["6 Plan"],
    "app/analysis/rewriter.py": ["7 Rewrite"],
    "app/analysis/change_proposal.py": ["7 Rewrite"],
    "app/llm/client.py": ["3 JD analysis", "7 Rewrite"],
    "app/llm/schemas.py": ["3 JD analysis", "7 Rewrite"],
    "app/validation/factual.py": ["8 Validate"],
    "app/validation/structural.py": ["8 Validate"],
    "app/validation/output.py": ["8 Validate"],
    "app/validation/content_lint.py": ["8 Validate"],
    "app/rendering/docx_patcher.py": ["9 Render"],
    "app/rendering/document_map.py": ["1 Ingest", "9 Render"],
    "app/rendering/template_renderer.py": ["9 Render"],
    "app/rendering/html_renderer.py": ["9 Render"],
    "app/rendering/layout.py": ["9 Render"],
    "app/rendering/page_fit.py": ["9 Render"],
    "app/rendering/review_view.py": ["7 Rewrite"],
    "app/rendering/pdf_converter.py": ["9 Render"],
    "app/services/run_manager.py": ["10 Report"],
    "app/api/sessions.py": ["10 Report"],
    "app/api/forms.py": ["7 Rewrite", "10 Report"],
    "app/services/profile_store.py": ["7 Rewrite"],
    "app/services/tailor.py": STAGES,  # the orchestrator touches every stage
    "app/ui.py": STAGES,
    "app/cli.py": STAGES,
    "app/api/main.py": STAGES,
    "app/api/routes.py": STAGES,
    "app/config/settings.py": [],
    "app/eval/__init__.py": [],
    "app/eval/__main__.py": [],
    "app/eval/harness.py": STAGES,  # runs the whole pipeline per case
    "app/eval/golden.py": ["2 Normalize"],
    "app/eval/judge.py": ["7 Rewrite", "8 Validate"],
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def git(*args: str, check: bool = True) -> str:
    res = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def layer_of(path: str) -> str:
    for prefix, name in LAYERS:
        if path == prefix or path.startswith(prefix):
            return name
    return "Root"


def module_name(path: str) -> Optional[str]:
    if not path.endswith(".py"):
        return None
    mod = path[:-3].replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


def first_line(doc: Optional[str]) -> str:
    if not doc:
        return ""
    for line in doc.strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def list_files() -> List[str]:
    """Tracked + new (not ignored) files, restricted to the project map."""
    out = git("ls-files", "--cached", "--others", "--exclude-standard")
    files = []
    for f in out.splitlines():
        if not os.path.exists(os.path.join(ROOT, f)):
            continue  # deleted in the working tree
        if f.startswith(SCAN_PREFIXES) or f in ROOT_FILES:
            if "__pycache__" in f:
                continue
            files.append(f)
    return sorted(set(files))


# ---------------------------------------------------------------------------
# Python structure extraction (shared by the graph and the change log)
# ---------------------------------------------------------------------------

def parse_python(source: str) -> Optional[dict]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    info = {"doc": first_line(ast.get_docstring(tree)), "classes": [], "functions": [], "imports": set()}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                {"name": n.name, "line": n.lineno, "doc": first_line(ast.get_docstring(n))}
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            info["classes"].append(
                {"name": node.name, "line": node.lineno, "doc": first_line(ast.get_docstring(node)), "methods": methods}
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info["functions"].append({"name": node.name, "line": node.lineno, "doc": first_line(ast.get_docstring(node))})
    # imports anywhere in the file (tailor.py imports lazily inside functions)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            info["imports"].add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                info["imports"].add(alias.name)
    return info


def symbols_of(info: Optional[dict]) -> Set[str]:
    if not info:
        return set()
    out = set()
    for c in info["classes"]:
        out.add(f"class {c['name']}")
        for m in c["methods"]:
            out.add(f"{c['name']}.{m['name']}()")
    for f in info["functions"]:
        out.add(f"{f['name']}()")
    return out


def settings_fields(source: str) -> List[dict]:
    tree = ast.parse(source)
    fields = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    name = stmt.target.id
                    if name == "model_config":
                        continue
                    default = ast.unparse(stmt.value) if stmt.value is not None else ""
                    fields.append({"name": name, "env": name.upper(), "type": ast.unparse(stmt.annotation), "default": default})
    return fields


# ---------------------------------------------------------------------------
# knowledge graph
# ---------------------------------------------------------------------------

def build_graph() -> dict:
    files = list_files()
    module_to_path = {module_name(f): f for f in files if f.endswith(".py")}
    prompt_files = [f for f in files if f.startswith("app/llm/prompts/")]

    nodes: List[dict] = []
    edges: List[dict] = []
    hasher = hashlib.sha256()
    settings: List[dict] = []

    for path in files:
        with open(os.path.join(ROOT, path), "rb") as fh:
            raw = fh.read()
        hasher.update(path.encode() + b"\0" + raw)
        kind = "prompt" if path in prompt_files else ("python" if path.endswith(".py") else "file")
        node = {
            "id": path,
            "type": kind,
            "layer": layer_of(path),
            "stages": STAGE_MAP.get(path, []),
            "lines": raw.count(b"\n"),
        }
        if path.endswith(".py"):
            text = raw.decode("utf-8", errors="replace")
            info = parse_python(text)
            if info:
                node["doc"] = info["doc"]
                node["classes"] = info["classes"]
                node["functions"] = info["functions"]
                for c in info["classes"]:
                    edges.append({"from": path, "to": f"{path}::{c['name']}", "type": "contains"})
                for imp in sorted(info["imports"]):
                    target = module_to_path.get(imp)
                    if target is None:
                        # "from app.x import y" where y is a submodule
                        target = next((module_to_path[m] for m in module_to_path if m and imp.startswith(m + ".")), None)
                    if target and target != path:
                        etype = "tested_by" if path.startswith("tests/") else "imports"
                        if etype == "tested_by":
                            edges.append({"from": target, "to": path, "type": "tested_by"})
                        else:
                            edges.append({"from": path, "to": target, "type": "imports"})
                for p in prompt_files:
                    if f'"{os.path.basename(p)}"' in text:
                        edges.append({"from": path, "to": p, "type": "uses_prompt"})
            if path == "app/config/settings.py":
                settings = settings_fields(raw.decode("utf-8"))
        nodes.append(node)

    # de-duplicate + sort edges for stable diffs
    uniq = {(e["from"], e["to"], e["type"]) for e in edges}
    edges = [{"from": a, "to": b, "type": t} for a, b, t in sorted(uniq)]

    py_nodes = [n for n in nodes if n["type"] == "python"]
    stats = {
        "files": len(nodes),
        "python_files": len(py_nodes),
        "app_modules": sum(1 for n in py_nodes if n["id"].startswith("app/")),
        "test_files": sum(1 for n in py_nodes if n["id"].startswith("tests/") and os.path.basename(n["id"]).startswith("test_")),
        "classes": sum(len(n.get("classes", [])) for n in py_nodes),
        "functions": sum(len(n.get("functions", [])) + sum(len(c["methods"]) for c in n.get("classes", [])) for n in py_nodes),
        "lines_of_python": sum(n["lines"] for n in py_nodes),
    }
    return {
        "schema": 1,
        "source_hash": hasher.hexdigest()[:16],
        "stats": stats,
        "axes": {"x": "location (path)", "y": "layer", "z": "pipeline stage", "layers": sorted({n for _, n in LAYERS}), "stages": STAGES},
        "settings": settings,
        "nodes": nodes,
        "edges": edges,
    }


def render_graph_md(g: dict) -> str:
    nodes = {n["id"]: n for n in g["nodes"]}
    by_type = defaultdict(lambda: defaultdict(list))
    for e in g["edges"]:
        by_type[e["type"]][e["from"]].append(e["to"])
    imported_by = defaultdict(list)
    for src, targets in by_type["imports"].items():
        for t in targets:
            imported_by[t].append(src)

    app_files = sorted(p for p in nodes if p.startswith("app/") and p.endswith(".py"))
    s = g["stats"]
    L: List[str] = []
    w = L.append

    w("# Knowledge Graph — Resume-optimizer")
    w("")
    w("> **Auto-generated** by `scripts/update_docs.py graph` (run by the pre-commit hook). Do not edit by hand —")
    w("> change the code, or the `STAGE_MAP` / `LAYERS` tables in the script. Machine-readable twin: `KNOWLEDGE_GRAPH.json`.")
    w("")
    w(f"**{s['app_modules']} app modules · {s['test_files']} test files · {s['classes']} classes · "
      f"{s['functions']} functions/methods · {s['lines_of_python']:,} lines of Python** · source hash `{g['source_hash']}`")
    w("")
    w("How to read this: every file sits at a point in a 3-D space — **where** it lives (path), **what** it is (layer), "
      "and **when** it runs (pipeline stage). Section 2 is that matrix; section 3 zooms into each module.")
    w("")
    w("## Contents")
    w("1. [Directory map](#1-directory-map)")
    w("2. [Layer × Stage matrix](#2-layer--stage-matrix)")
    w("3. [Module cards](#3-module-cards)")
    w("4. [Dependency diagram](#4-dependency-diagram)")
    w("5. [Configuration keys](#5-configuration-keys)")
    w("6. [Prompts](#6-prompts)")
    w("7. [Gaps: untested and unmapped modules](#7-gaps-untested-and-unmapped-modules)")
    w("")

    # 1. directory map ------------------------------------------------------
    w("## 1. Directory map")
    w("")
    w("```text")
    tree: Dict[str, List[str]] = defaultdict(list)
    for p in sorted(nodes):
        d = os.path.dirname(p)
        tree[d].append(os.path.basename(p))
        while d:  # make sure folders holding only sub-folders are printed too
            d = os.path.dirname(d)
            tree.setdefault(d, [])
    for d in sorted(tree):
        depth = 0 if not d else d.count("/") + 1
        if d:
            w(f"{'  ' * (depth - 1)}{os.path.basename(d)}/")
        for fname in tree[d]:
            n = nodes[os.path.join(d, fname) if d else fname]
            note = n.get("doc") or ""
            if not note and n.get("classes"):
                note = ", ".join(c["name"] for c in n["classes"])
            if not note and n.get("functions"):
                note = ", ".join(f"{f['name']}()" for f in n["functions"])
            note = (note[:70] + "…") if len(note) > 71 else note
            label = f"{'  ' * depth}{fname}"
            w(f"{label:<48} {note}".rstrip())
    w("```")
    w("")

    # 2. matrix -------------------------------------------------------------
    w("## 2. Layer × Stage matrix")
    w("")
    w("Rows = layer (what kind of code), columns = pipeline stage (when it runs during a tailoring run). "
      "Orchestrators (`tailor.py`, `ui.py`, `cli.py`) span every stage and are listed once below the table.")
    w("")
    spanning = [p for p in app_files if nodes[p]["stages"] == STAGES]
    layers_present = [ly for ly in dict.fromkeys(n for _, n in LAYERS) if any(nodes[p]["layer"] == ly for p in app_files)]
    w("| Layer | " + " | ".join(STAGES) + " |")
    w("|---|" + "---|" * len(STAGES))
    for ly in layers_present:
        row = []
        for st in STAGES:
            cell = [os.path.basename(p)[:-3] for p in app_files
                    if nodes[p]["layer"] == ly and st in nodes[p]["stages"] and p not in spanning]
            row.append("<br>".join(f"`{c}`" for c in cell) or "·")
        if any(c != "·" for c in row):
            w(f"| **{ly}** | " + " | ".join(row) + " |")
    w("")
    w("Spanning all stages: " + ", ".join(f"`{p}`" for p in spanning))
    w("")

    # 3. module cards -------------------------------------------------------
    w("## 3. Module cards")
    w("")
    for p in app_files:
        n = nodes[p]
        w(f"### `{p}`")
        w("")
        meta = [f"**Layer:** {n['layer']}", f"**Stage:** {', '.join(n['stages']) if n['stages'] and n['stages'] != STAGES else ('all' if n['stages'] else '—')}", f"**Lines:** {n['lines']}"]
        w(" · ".join(meta))
        if n.get("doc"):
            w("")
            w(f"_{n['doc']}_")
        w("")
        for c in n.get("classes", []):
            w(f"- class **`{c['name']}`** ([{p}:{c['line']}](../{p}#L{c['line']})){' — ' + c['doc'] if c['doc'] else ''}")
            for m in c["methods"]:
                if m["name"].startswith("__") and m["name"] != "__init__":
                    continue
                w(f"  - `{m['name']}()` :{m['line']}{' — ' + m['doc'] if m['doc'] else ''}")
        for f in n.get("functions", []):
            w(f"- function **`{f['name']}()`** ([{p}:{f['line']}](../{p}#L{f['line']})){' — ' + f['doc'] if f['doc'] else ''}")
        rel = [
            ("Imports", by_type["imports"].get(p, [])),
            ("Imported by", imported_by.get(p, [])),
            ("Tested by", by_type["tested_by"].get(p, [])),
            ("Prompts", by_type["uses_prompt"].get(p, [])),
        ]
        for label, items in rel:
            if items:
                w(f"- **{label}:** " + ", ".join(f"`{os.path.relpath(i, 'app') if i.startswith('app/') else i}`" for i in sorted(items)))
        w("")

    # 4. mermaid ------------------------------------------------------------
    w("## 4. Dependency diagram")
    w("")
    w("Arrows point from importer to imported module (app code only; domain models omitted for readability, "
      "since almost everything imports them).")
    w("")
    w("```mermaid")
    w("flowchart LR")
    by_layer = defaultdict(list)
    for p in app_files:
        if nodes[p]["layer"] != "Domain models" and not p.endswith("__init__.py"):
            by_layer[nodes[p]["layer"]].append(p)
    ident = lambda p: re.sub(r"[^A-Za-z0-9]", "_", p[4:-3])
    for ly in sorted(by_layer):
        w(f"  subgraph {re.sub(r'[^A-Za-z]', '', ly)}[{ly}]")
        for p in by_layer[ly]:
            w(f"    {ident(p)}[{os.path.basename(p)[:-3]}]")
        w("  end")
    for src in app_files:
        for t in sorted(by_type["imports"].get(src, [])):
            if t in app_files and nodes[src]["layer"] != "Domain models" and nodes[t]["layer"] != "Domain models":
                w(f"  {ident(src)} --> {ident(t)}")
    w("```")
    w("")

    # 5. settings -----------------------------------------------------------
    w("## 5. Configuration keys")
    w("")
    w("From `app/config/settings.py`; each can be overridden by the env var of the same name in `.env`.")
    w("")
    w("| Env var | Type | Default |")
    w("|---|---|---|")
    for f in g["settings"]:
        w(f"| `{f['env']}` | {f['type']} | `{f['default']}` |")
    w("")

    # 6. prompts ------------------------------------------------------------
    w("## 6. Prompts")
    w("")
    users = defaultdict(list)
    for src, targets in by_type["uses_prompt"].items():
        for t in targets:
            users[t].append(src)
    w("| Prompt file | Loaded by |")
    w("|---|---|")
    for p in sorted(x for x in nodes if nodes[x]["type"] == "prompt"):
        w(f"| `{os.path.basename(p)}` | {', '.join(f'`{u}`' for u in users.get(p, [])) or '**unused**'} |")
    w("")

    # 7. gaps ---------------------------------------------------------------
    w("## 7. Gaps: untested and unmapped modules")
    w("")
    untested = [p for p in app_files if not by_type["tested_by"].get(p) and not p.endswith("__init__.py")]
    unmapped = [p for p in app_files if p not in STAGE_MAP and not p.endswith("__init__.py")]
    w("**No test file imports these directly** (they may still be exercised indirectly):")
    w("")
    for p in untested:
        w(f"- `{p}`")
    if not untested:
        w("- none")
    w("")
    entry_points = {"app/ui.py", "app/cli.py", "app/api/main.py"}
    orphans = [p for p in app_files if p not in entry_points and not imported_by.get(p) and not p.endswith("__init__.py")]
    w("**Not imported by any app code** (possibly dead code, or only used by tests/scripts):")
    w("")
    for p in orphans:
        w(f"- `{p}`")
    if not orphans:
        w("- none")
    w("")
    w("**Not in `STAGE_MAP`** (add them in `scripts/update_docs.py`):")
    w("")
    for p in unmapped:
        w(f"- `{p}`")
    if not unmapped:
        w("- none")
    w("")
    return "\n".join(L)


def write_graph(check: bool = False) -> int:
    g = build_graph()
    new_json = json.dumps(g, indent=2, sort_keys=False) + "\n"
    new_md = render_graph_md(g)
    if check:
        stale = []
        for path, content in ((GRAPH_JSON, new_json), (GRAPH_MD, new_md)):
            try:
                with open(path, encoding="utf-8") as fh:
                    if fh.read() != content:
                        stale.append(path)
            except FileNotFoundError:
                stale.append(path)
        for p in stale:
            print(f"out of date: {os.path.relpath(p, ROOT)}")
        return 1 if stale else 0
    os.makedirs(DOCS_DIR, exist_ok=True)
    for path, content in ((GRAPH_JSON, new_json), (GRAPH_MD, new_md)):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    return 0


# ---------------------------------------------------------------------------
# change log
# ---------------------------------------------------------------------------

LOG_HEADER = """# Change Log — Resume-optimizer

Timestamped record of every **major** commit (anything touching `app/`, `scripts/`, `tests/`, `.githooks/` or
`pyproject.toml`), newest first. Entries are written automatically by the post-commit hook
(`scripts/update_docs.py log-entry`); docs-only commits and commits containing `[skip log]` are skipped.

- **Why** comes from the commit message body, so write one for anything non-trivial.
- **Structure delta** is computed from the code itself: classes and functions added or removed.
- You may hand-edit an entry to add context; the hook only rewrites an entry when that same commit is amended.

<!-- entries below; newest first -->
"""
ENTRY_MARK = "<!-- entry:{key} -->"
TRAILER_RE = re.compile(r"^(Co-Authored-By|Claude-Session|Signed-off-by):", re.I)


def commit_info(rev: str) -> dict:
    fmt = "%H%x00%h%x00%an%x00%aI%x00%s%x00%b%x00%P"
    out = git("show", "-s", f"--format={fmt}", rev)
    full, short, author, adate, subject, body, parents = out.split("\x00")
    body_lines = [ln for ln in body.strip().splitlines() if not TRAILER_RE.match(ln.strip())]
    return {
        "hash": full, "short": short, "author": author, "date": adate, "subject": subject.strip(),
        "body": "\n".join(body_lines).strip(), "parents": parents.split(),
    }


def changed_files(rev: str, parents: List[str]) -> List[Tuple[str, str]]:
    if parents:
        out = git("diff", "--name-status", "--no-renames", parents[0], rev)
    else:
        out = git("show", "--name-status", "--no-renames", "--format=", rev)
    rows = []
    for line in out.splitlines():
        if "\t" in line:
            status, path = line.split("\t", 1)
            rows.append((status[0], path))
    return rows


def is_major(rev: str) -> bool:
    info = commit_info(rev)
    if len(info["parents"]) > 1:
        return False  # merge commits
    if SKIP_LOG_MARKER in (info["subject"] + info["body"]).lower():
        return False
    return any(p.startswith(MAJOR_PREFIXES) or p.endswith(".py") for _, p in changed_files(rev, info["parents"]))


def blob(rev: str, path: str) -> Optional[str]:
    res = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True)
    return res.stdout.decode("utf-8", errors="replace") if res.returncode == 0 else None


def structure_delta(rev: str, parents: List[str], files: List[Tuple[str, str]]) -> List[str]:
    lines = []
    for status, path in files:
        if not path.endswith(".py") or not path.startswith(("app/", "scripts/")):
            continue
        old = symbols_of(parse_python(blob(parents[0], path))) if parents and status != "A" and blob(parents[0], path) else set()
        new = symbols_of(parse_python(blob(rev, path))) if status != "D" and blob(rev, path) else set()
        added, removed = sorted(new - old), sorted(old - new)
        if status == "A":
            lines.append(f"- new module `{path}`" + (f": {', '.join(f'`{a}`' for a in added if a.startswith('class '))}" if any(a.startswith("class ") for a in added) else ""))
        elif status == "D":
            lines.append(f"- removed module `{path}`")
        else:
            parts = []
            if added:
                parts.append("added " + ", ".join(f"`{a}`" for a in added))
            if removed:
                parts.append("removed " + ", ".join(f"`{r}`" for r in removed))
            if parts:
                lines.append(f"- `{path}`: " + "; ".join(parts))
    return lines


def render_entry(rev: str, with_branch: bool = True) -> Tuple[str, str]:
    info = commit_info(rev)
    files = changed_files(rev, info["parents"])
    local = datetime.fromisoformat(info["date"]).astimezone()
    key = info["date"]  # author date survives `git commit --amend`, the hash does not
    branch = git("rev-parse", "--abbrev-ref", "HEAD", check=False).strip() if with_branch else ""

    out = [ENTRY_MARK.format(key=key)]
    out.append(f"## {local:%Y-%m-%d %H:%M} ({local:%z}) · {info['subject']}")
    out.append("")
    # A live entry is written by post-commit and then amended into the commit,
    # which changes the hash -- so only historical (backfilled) entries show one.
    out.append((f"{info['author']} · branch `{branch}`") if with_branch else f"`{info['short']}` · {info['author']}")
    out.append("")
    if info["body"]:
        out.append("**Why / details**")
        out.append("")
        out.extend("> " + ln if ln.strip() else ">" for ln in info["body"].splitlines())
        out.append("")

    shown = [(s, p) for s, p in files if not p.startswith(".venv") and p not in GENERATED_DOCS]
    hidden = sum(1 for _, p in files if p.startswith(".venv"))
    if shown:
        out.append("**Changed files**")
        out.append("")
        grouped = defaultdict(list)
        for s, p in shown:
            grouped[layer_of(p)].append(f"`{s}` {p}")
        for ly in sorted(grouped):
            out.append(f"- {ly}: " + ", ".join(grouped[ly]))
        if hidden:
            out.append(f"- _(+{hidden} virtualenv files omitted)_")
        out.append("")

    delta = structure_delta(rev, info["parents"], files)
    if delta:
        out.append("**Structure delta**")
        out.append("")
        out.extend(delta)
        out.append("")
    return key, "\n".join(out).rstrip() + "\n"


def _split_entries(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    marker = "<!-- entries below; newest first -->"
    head, _, rest = text.partition(marker)
    head = head + marker + "\n"
    entries = []
    for chunk in re.split(r"(?=^<!-- entry:)", rest, flags=re.M):
        m = re.match(r"<!-- entry:(.+?) -->", chunk)
        if m:
            entries.append((m.group(1), chunk.strip() + "\n"))
    return head, entries


def _join(head: str, entries: List[Tuple[str, str]]) -> str:
    return head + "\n" + "\n---\n\n".join(e for _, e in entries)


def log_entry(rev: str) -> int:
    key, entry = render_entry(rev)
    if os.path.exists(CHANGE_LOG):
        with open(CHANGE_LOG, encoding="utf-8") as fh:
            head, entries = _split_entries(fh.read())
    else:
        head, entries = LOG_HEADER, []
    existing = [k for k, _ in entries]
    if key in existing:
        entries[existing.index(key)] = (key, entry)  # the same commit was amended
    else:
        entries.insert(0, (key, entry))
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(CHANGE_LOG, "w", encoding="utf-8") as fh:
        fh.write(_join(head, entries))
    return 0


def backfill(force: bool) -> int:
    if os.path.exists(CHANGE_LOG) and not force:
        print("docs/CHANGE_LOG.md already exists (it may contain hand-written notes); pass --force to rebuild it.")
        return 1
    revs = git("rev-list", "HEAD").split()
    entries = []
    for rev in revs:  # newest first
        if is_major(rev):
            entries.append(render_entry(rev, with_branch=False))
    with open(CHANGE_LOG, "w", encoding="utf-8") as fh:
        fh.write(_join(LOG_HEADER, entries))
    print(f"wrote {len(entries)} entries ({len(revs) - len(entries)} non-major commits skipped)")
    return 0


# ---------------------------------------------------------------------------

def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("graph")
    g.add_argument("--check", action="store_true")
    for name in ("log-entry", "is-major"):
        p = sub.add_parser(name)
        p.add_argument("rev", nargs="?", default="HEAD")
    b = sub.add_parser("backfill")
    b.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "graph":
        return write_graph(check=args.check)
    if args.cmd == "log-entry":
        return log_entry(args.rev)
    if args.cmd == "is-major":
        return 0 if is_major(args.rev) else 1
    if args.cmd == "backfill":
        return backfill(args.force)
    return 2


if __name__ == "__main__":
    sys.exit(main())
