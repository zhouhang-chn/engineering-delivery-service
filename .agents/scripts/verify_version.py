#!/usr/bin/env python3
"""Version completeness gate script.

Usage:
    uv run python .agents/scripts/verify_version.py v0.1-single-worker-e2e

Checks all quality gates defined in the development-workflow skill before a
version can be marked COMPLETE. Exits 0 if all gates pass, 1 otherwise.

Checks performed:
 1. implementation-notes.md exists and is filled (no placeholders)
 2. All required sections present in implementation-notes.md
 3. action-plan.md exists and all tasks are marked complete
 4. No TODO/FIXME/HACK/XXX in production Python code
 5. ruff check passes
 6. pytest passes
 7. milestones.md marks the version as COMPLETE
 8. Public classes/functions have docstrings (AST-based)
 9. README.md architectural claims match declared dependencies
10. Core dependencies importable
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── helpers ──────────────────────────────────────────────────────────────────

# Resolve PROJECT_ROOT: handle both .agents/scripts/ and scripts/
_this_dir = Path(__file__).resolve().parent
if _this_dir.parent.name == ".agents":
    PROJECT_ROOT = _this_dir.parent.parent
else:
    PROJECT_ROOT = _this_dir.parent

DOCS_DIR = PROJECT_ROOT / "docs"
VERSIONS_DIR = DOCS_DIR / "versions"
MILESTONES_FILE = DOCS_DIR / "milestones.md"
PRODUCTION_DIRS = [
    "agent",
    "a2a_api",
    "tools",
    "control",
    "codex",
    "sandbox",
    "deployment",
    "db",
]

# Patterns that indicate unfilled implementation notes
PLACEHOLDER_PATTERNS = [
    r"\(pending\)",
    r"\*To be filled",
    r"pending implementation",
]

REQUIRED_NOTE_SECTIONS = [
    "## Key Decisions",
    "## Deviations from Design",
    "## Bugs Encountered",
    "## Lessons Learned",
]

# Conversational/thinking comment patterns (case-insensitive)
THINKING_COMMENT_PATTERNS = [
    r"actually,? let",
    r"wait,?",
    r"^#\s*hmm",
    r"\btodo\b",
    r"\bfixme\b",
    r"\bhack\b",
    r"\bxxx\b",
]

PASS = "✓"
FAIL = "✗"
WARN = "!"

failures: list[str] = []
warnings: list[str] = []
checks_passed = 0
checks_total = 0


def ruff_bin() -> str:
    """Prefer the project venv's ruff so the gate works without a global install."""
    venv_ruff = PROJECT_ROOT / ".venv" / "bin" / "ruff"
    if venv_ruff.exists():
        return str(venv_ruff)
    return shutil.which("ruff") or "ruff"


def check(name: str, passed: bool, detail: str = "") -> None:
    """Record a check result."""
    global checks_passed, checks_total
    checks_total += 1
    if passed:
        checks_passed += 1
        print(f"  {PASS} {name}")
    else:
        failures.append(f"{name}: {detail}" if detail else name)
        print(f"  {FAIL} {name}")
        if detail:
            print(f"      → {detail}")


def warn(name: str, detail: str = "") -> None:
    """Record a warning."""
    warnings.append(f"{name}: {detail}" if detail else name)
    print(f"  {WARN} {name}")
    if detail:
        print(f"      → {detail}")


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[bool, str]:
    """Run a command and return (success, output).

    A timeout is reported as a failed check rather than propagating, so one
    slow command cannot abort every remaining check in the gate.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {' '.join(cmd)}"
    output = result.stdout + result.stderr
    return result.returncode == 0, output.strip()


# ── gate checks ──────────────────────────────────────────────────────────────


def iter_production_files():
    for pkg_dir in PRODUCTION_DIRS:
        pkg_path = PROJECT_ROOT / pkg_dir
        if pkg_path.is_dir():
            yield from sorted(pkg_path.rglob("*.py"))


def check_implementation_notes(version_dir: Path) -> None:
    """Check implementation-notes.md exists and is properly filled."""
    notes_path = version_dir / "implementation-notes.md"

    passed = notes_path.exists()
    check(f"implementation-notes.md exists ({notes_path.relative_to(PROJECT_ROOT)})", passed)
    if not passed:
        return

    content = notes_path.read_text(encoding="utf-8")

    # Check for placeholder text
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            check(
                "implementation-notes.md contains no placeholder text",
                False,
                f"Found placeholder matching '{pattern}'",
            )
            break
    else:
        check("implementation-notes.md contains no placeholder text", True)

    # Check required sections exist
    for section in REQUIRED_NOTE_SECTIONS:
        if section not in content:
            check(f"Section '{section}' present", False, "Section heading not found")
        else:
            # Check section has content (not just the heading)
            idx = content.index(section)
            after = content[idx + len(section) :]
            # Get text until next ## or end
            next_section = re.search(r"\n## ", after)
            section_body = after[: next_section.start()] if next_section else after
            # Body should have some non-empty, non-placeholder content
            body_clean = re.sub(r"[#*\s]", "", section_body)
            if len(body_clean) < 20:
                check(f"Section '{section}' has content", False, "Section appears empty")
            else:
                check(f"Section '{section}' has content", True)

    # Check action-plan.md
    plan_path = version_dir / "action-plan.md"
    plan_passed = plan_path.exists()
    check(f"action-plan.md exists ({plan_path.relative_to(PROJECT_ROOT)})", plan_passed)
    if plan_passed:
        plan_content = plan_path.read_text(encoding="utf-8")
        unchecked_tasks = re.findall(r"- \[ \]\s+(.+)", plan_content)
        if unchecked_tasks:
            check(
                "action-plan.md tasks all marked complete",
                False,
                f"Found {len(unchecked_tasks)} uncompleted task(s): "
                f"e.g. '{unchecked_tasks[0][:50]}...'",
            )
        else:
            check("action-plan.md tasks all marked complete", True)

    # Check iterations if iterations.md exists
    iter_md_path = version_dir / "iterations.md"
    if iter_md_path.exists():
        iterations_dir = version_dir / "iterations"
        has_iter_dir = iterations_dir.is_dir()
        check(f"iterations/ directory exists ({version_dir.name})", has_iter_dir)
        if has_iter_dir:
            # Parse declared iteration names from iterations.md
            iter_md_text = iter_md_path.read_text(encoding="utf-8")
            declared_iters = re.findall(r"\*\*(v\d+\.\d+\.\d+-[a-z0-9-]+)\*\*", iter_md_text)
            if not declared_iters:
                declared_iters = re.findall(r"(v\d+\.\d+\.\d+-[a-z0-9-]+)", iter_md_text)
            for iter_name in sorted(set(declared_iters)):
                iter_dir = iterations_dir / iter_name
                check(f"  Iteration folder {iter_name} exists", iter_dir.is_dir())
                if iter_dir.is_dir():
                    for req_file in (
                        "gap-analysis.md",
                        "design.md",
                        "action-plan.md",
                        "implementation-notes.md",
                    ):
                        rf_path = iter_dir / req_file
                        check(f"    {iter_name}/{req_file} exists", rf_path.exists())
                        if req_file == "implementation-notes.md" and rf_path.exists():
                            iter_content = rf_path.read_text(encoding="utf-8")
                            has_placeholder = any(
                                re.search(p, iter_content, re.IGNORECASE)
                                for p in PLACEHOLDER_PATTERNS
                            )
                            check(f"    {iter_name}/{req_file} filled", not has_placeholder)
                        if req_file == "action-plan.md" and rf_path.exists():
                            iter_unchecked = re.findall(r"- \[ \]", rf_path.read_text(encoding="utf-8"))
                            check(
                                f"    {iter_name} action-plan tasks all checked",
                                not iter_unchecked,
                                f"{len(iter_unchecked)} unchecked task(s) remain",
                            )


def check_no_todos() -> None:
    """Check for TODO/FIXME/HACK/XXX in production code."""
    found = []
    for py_file in iter_production_files():
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line):
                rel = py_file.relative_to(PROJECT_ROOT)
                found.append(f"  {rel}:{i}: {line.strip()}")
    passed = len(found) == 0
    check("No TODO/FIXME/HACK/XXX in production code", passed)
    if not passed:
        for f in found[:10]:
            print(f"      {f}")


def check_no_thinking_comments() -> None:
    """Check for conversational/thinking comments in code."""
    found = []
    for py_file in iter_production_files():
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            comment_text = stripped.lstrip("# ").strip().lower()
            for pattern in THINKING_COMMENT_PATTERNS:
                if re.search(pattern, comment_text, re.IGNORECASE):
                    # Skip shebang / encoding declarations
                    if "coding" in comment_text or "!/usr/bin" in comment_text:
                        continue
                    rel = py_file.relative_to(PROJECT_ROOT)
                    found.append(f"  {rel}:{i}: {line.strip()}")
                    break
    if found:
        warn("Conversational/thinking comments found (review and clean up)", "\n".join(found[:5]))
    else:
        check("No conversational thinking comments in code", True)


def check_ruff() -> None:
    """Run ruff check."""
    passed, output = run_cmd([ruff_bin(), "check", "."])
    check("ruff check passes", passed, output if not passed else "")


def check_pytest() -> None:
    """Run pytest."""
    passed, output = run_cmd(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        timeout=600,
    )
    check("pytest passes (all tests)", passed)
    if not passed:
        for line in output.splitlines()[-10:]:
            print(f"      {line}")


def check_milestones(version_name: str) -> None:
    """Check milestones.md marks version as COMPLETE."""
    if not MILESTONES_FILE.exists():
        check("milestones.md exists", False, "File not found")
        return
    content = MILESTONES_FILE.read_text(encoding="utf-8")
    names_to_check = [
        version_name,
        Path(version_name).name,
        Path(version_name).name.split("-")[0],
    ]
    found_complete = False
    for line in content.splitlines():
        if any(name in line for name in names_to_check) and "COMPLETE" in line:
            found_complete = True
            break
        if any(
            re.search(rf"Completed.*{re.escape(name)}", line, re.IGNORECASE)
            for name in names_to_check
        ):
            found_complete = True
            break
    check(
        f"milestones.md marks {version_name} as COMPLETE",
        found_complete,
        "Add COMPLETE status and date to milestones.md",
    )


def check_docstrings() -> None:
    """Check that public classes and functions have docstrings."""
    missing: list[str] = []
    for py_file in iter_production_files():
        if py_file.name.startswith("__init__"):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                if not docstring or len(docstring.strip()) < 5:
                    rel = py_file.relative_to(PROJECT_ROOT)
                    missing.append(f"  {rel}:{node.lineno}: class {node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private methods (_name) and dunder methods (__name__)
                if node.name.startswith("_"):
                    continue
                docstring = ast.get_docstring(node)
                if not docstring or len(docstring.strip()) < 5:
                    rel = py_file.relative_to(PROJECT_ROOT)
                    missing.append(f"  {rel}:{node.lineno}: {node.name}()")
    passed = len(missing) == 0
    check("Public classes/functions have docstrings", passed)
    if not passed:
        for m in missing[:15]:
            print(f"      {m}")
        if len(missing) > 15:
            print(f"      ... and {len(missing) - 15} more")


def check_no_duplicate_stateful_init() -> None:
    """Heuristic check: flag __init__ methods that instantiate the same class twice."""
    found = []
    for py_file in iter_production_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                constructed: dict[str, int] = {}
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                        name = child.func.id
                        constructed[name] = constructed.get(name, 0) + 1
                duplicates = {k: v for k, v in constructed.items() if v > 1}
                if duplicates:
                    rel = py_file.relative_to(PROJECT_ROOT)
                    for cls_name, count in duplicates.items():
                        if cls_name in ("Path", "Check", "list", "dict", "set"):
                            continue
                        found.append(
                            f"  {rel}: {cls_name} constructed {count} times in __init__"
                        )
    if found:
        warn("Potential duplicate stateful component instantiation", "\n".join(found))


def check_packaging() -> None:
    """Validate core dependencies are resolvable in the current environment."""
    required_deps = [
        "google.adk",
        "a2a",
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg",
        "alembic",
        "docker",
        "pydantic",
    ]
    missing = []
    for mod in required_deps:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    check("Core package dependencies resolvable", len(missing) == 0, f"Missing: {missing}")


def check_readme_claims() -> None:
    """Verify every framework README.md claims as a foundation is actually a dependency.

    Rule: if the README's opening section names a framework, its distribution
    must appear in ``[project].dependencies``, or the sentence naming it must
    mark it as planned (a "vX.Y" reference, or the words "landing"/"planned"/
    "roadmap").
    """
    readme = PROJECT_ROOT / "README.md"
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not readme.exists() or not pyproject.exists():
        check(
            "README.md architectural claims verifiable",
            False,
            "Missing README.md or pyproject.toml",
        )
        return

    # Framework display name -> distribution name expected in [project].dependencies
    frameworks = {
        "Google ADK": "google-adk",
        "LangChain": "langchain",
        "LangGraph": "langgraph",
        "LlamaIndex": "llama-index",
    }

    content = readme.read_text(encoding="utf-8")
    # The "hero" section: everything before the first level-2 heading.
    hero = content.split("\n## ", 1)[0]

    deps_block = pyproject.read_text(encoding="utf-8")
    match = re.search(r"^dependencies\s*=\s*\[(.*?)\]", deps_block, re.DOTALL | re.MULTILINE)
    declared = match.group(1).lower() if match else ""

    planned_marker = re.compile(r"v\d+\.\d+|landing|planned|roadmap", re.IGNORECASE)
    unsupported = []
    for display_name, dist in frameworks.items():
        if display_name.lower() not in hero.lower():
            continue
        if dist.lower() in declared:
            continue
        # Not a declared dependency: every sentence naming it must mark it as planned.
        sentences = [
            s for s in re.split(r"(?<=[.!?])\s+", hero) if display_name.lower() in s.lower()
        ]
        if not all(planned_marker.search(s) for s in sentences):
            unsupported.append(display_name)

    check(
        "README.md architectural claims match declared dependencies",
        not unsupported,
        f"README names {unsupported} as foundational, but they are neither in "
        f"[project].dependencies nor marked as planned (vX.Y / landing / planned / roadmap)",
    )


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: uv run python .agents/scripts/verify_version.py <version-dir>")
        print("Example: uv run python .agents/scripts/verify_version.py v0.1-single-worker-e2e")
        print()
        print("Available versions:")
        if VERSIONS_DIR.is_dir():
            for d in sorted(VERSIONS_DIR.iterdir()):
                if d.is_dir():
                    print(f"  {d.name}")
        return 1

    version_name = sys.argv[1]
    version_dir = VERSIONS_DIR / version_name

    if not version_dir.is_dir():
        print(f"{FAIL} Version directory not found: {version_dir}")
        return 1

    print("=" * 60)
    print(f"VERSION COMPLETENESS GATE: {version_name}")
    print("=" * 60)
    print()

    print("📝 Documentation checks:")
    check_implementation_notes(version_dir)
    check_milestones(version_name)
    print()

    print("🔍 Code quality & architecture checks:")
    check_no_todos()
    check_no_thinking_comments()
    check_docstrings()
    check_no_duplicate_stateful_init()
    print()

    print("🛠️  Build & test checks:")
    check_packaging()
    check_readme_claims()
    check_ruff()
    check_pytest()
    print()

    print("=" * 60)
    print(f"Results: {checks_passed}/{checks_total} checks passed")
    if warnings:
        print(f"         {len(warnings)} warning(s)")
    print("=" * 60)

    if failures:
        print()
        print(f"{FAIL} FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  • {f}")

    if warnings:
        print()
        print(f"{WARN} WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  • {w}")

    if failures:
        print()
        print("❌ Version is NOT ready to be marked COMPLETE. Fix failures above.")
        return 1
    else:
        print()
        if warnings:
            print("✅ All checks pass (with warnings). Version can be marked COMPLETE.")
        else:
            print("✅ All checks pass. Version is COMPLETE.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
