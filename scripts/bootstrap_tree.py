from __future__ import annotations

import argparse
import shutil
from pathlib import Path

try:
    from .state import merge_state
except ImportError:  # pragma: no cover - direct script execution
    from state import merge_state


DOC_DIRS = [
    "product",
    "architecture",
    "ui",
    "api",
    "backend",
    "frontend",
    "tests",
    "decisions",
    "development",
    "agent-workflow",
]

RUNTIME_BIN_FILES = [
    "governance",
    "governance-init",
    "governance-verify",
]

RUNTIME_SCRIPT_FILES = [
    "__init__.py",
    "bootstrap_tree.py",
    "check_env.py",
    "governance_cli.py",
    "state.py",
    "verify_governance.py",
]


def _safe_write(path: Path, content: str, force: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")


def _copy_runtime_file(source: Path, target: Path, force: bool = False) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == target.resolve():
        return
    if target.exists() and not force:
        return
    shutil.copy2(source, target)


def _install_runtime(root: Path, force: bool = False) -> None:
    pack_root = Path(__file__).resolve().parents[1]
    for name in RUNTIME_BIN_FILES:
        _copy_runtime_file(pack_root / "bin" / name, root / "bin" / name, force)
    for name in RUNTIME_SCRIPT_FILES:
        _copy_runtime_file(pack_root / "scripts" / name, root / "scripts" / name, force)


def _copy_source(product_doc: Path, source_dir: Path, force: bool = False) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / product_doc.name
    if target.exists() and not force:
        return target
    shutil.copy2(product_doc, target)
    return target


def _read_product_as_markdown(product_doc: Path, archived_rel: str) -> str:
    if product_doc.suffix.lower() in {".md", ".markdown"}:
        return product_doc.read_text(encoding="utf-8")
    return (
        "# Product Requirements Document\n\n"
        f"> 原始产品文档已归档到 `{archived_rel}`。\n\n"
        "## Conversion Required\n\n"
        "当前输入不是 Markdown。请使用工作流包中的产品文档归档流程，"
        "将原文转换为结构化 Markdown 后替换本文件正文。转换完成前，"
        "不得基于本文件派生 API、架构或任务计划。\n"
    )


def bootstrap(
    root: Path,
    product_doc: Path | None = None,
    force: bool = False,
    profile: str = "unknown",
    project_name: str | None = None,
) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    project_name = project_name or "Project Workspace"
    _install_runtime(root, force)

    _safe_write(
        root / "README.md",
        f"# {project_name}\n\n"
        "This repository was initialized with the docs-as-code governance workflow pack.\n\n"
        "## Start Here\n\n"
        "- Product source: `docs/product/core/PRD.md`\n"
        "- Documentation entry: `docs/README.md`\n"
        "- Governance rules: `AGENTS.md` and `docs/AGENTS.md`\n"
        "- Open questions: `docs/unresolved.md`\n"
        "- Delivery plan: `docs/development/README.md`\n",
        force,
    )
    _safe_write(
        root / "AGENTS.md",
        "# AGENTS.md\n\n"
        "> Scope: repository root and all subdirectories.\n\n"
        "## Source-of-Truth Priority\n\n"
        "1. `docs/product/core/PRD.md`\n"
        "2. `docs/product/core/product-meta.md`\n"
        "3. `docs/product/NN-*.md`\n"
        "4. `docs/api/`, `docs/architecture/`, `docs/ui/`, `docs/backend/`, `docs/frontend/`\n"
        "5. `docs/tests/`, `docs/development/`\n\n"
        "## Agent Rules\n\n"
        "- Read `docs/development/README.md` before implementation planning.\n"
        "- Register unresolved product, API, DB, or cross-module questions in `docs/unresolved.md` and ask.\n"
        "- Do not silently modify upstream product meaning in derived documents.\n"
        "- Keep generated code, task plans, and verification evidence traceable to specs.\n",
        force,
    )
    _safe_write(
        root / "SPEC.md",
        "# Project Spec Overview\n\n"
        "This file is a summary view. It must not become an independent source of truth.\n\n"
        "Canonical product sources:\n\n"
        "- `docs/product/core/PRD.md`\n"
        "- `docs/product/core/product-meta.md`\n",
        force,
    )
    _safe_write(
        root / "CONTRIBUTING.md",
        "# Contributing\n\n"
        "Use `docs/agent-workflow/task-handoff.md` for task handoff and completion criteria.\n",
        force,
    )
    _safe_write(
        root / "GOVERNANCE.md",
        "# Governance\n\n"
        "Repository governance is defined by `AGENTS.md`, `docs/AGENTS.md`, and domain-level `AGENTS.md` files.\n",
        force,
    )
    _safe_write(
        root / "SECURITY.md",
        "# Security\n\n"
        "Do not commit secrets. Authentication, authorization, and data boundary decisions must be documented before implementation.\n",
        force,
    )
    _safe_write(
        root / ".gitignore",
        "# Local caches\n"
        ".governance/\n"
        ".lycheecache\n"
        "__pycache__/\n"
        "*.pyc\n"
        "node_modules/\n"
        ".venv/\n",
        force,
    )
    _safe_write(
        root / "Makefile",
        ".PHONY: verify-governance check-env\n\n"
        "verify-governance:\n"
        "\tbin/governance verify .\n\n"
        "check-env:\n"
        "\tbin/governance env --target .\n",
        force,
    )

    for doc_dir in DOC_DIRS:
        (root / "docs" / doc_dir).mkdir(parents=True, exist_ok=True)

    _safe_write(root / "docs/README.md", _docs_readme(), force)
    _safe_write(root / "docs/AGENTS.md", _docs_agents(), force)
    _safe_write(root / "docs/unresolved.md", _unresolved(), force)
    _safe_write(root / "docs/glossary.md", _glossary(), force)

    _safe_write(root / "docs/product/README.md", _domain_readme("product", "产品需求与验收"), force)
    _safe_write(root / "docs/product/AGENTS.md", _domain_agents("product"), force)
    _safe_write(root / "docs/product/core/product-meta.md", _product_meta(), force)
    (root / "docs/product/core/source").mkdir(parents=True, exist_ok=True)

    for doc_dir in DOC_DIRS:
        if doc_dir == "product":
            continue
        _safe_write(root / f"docs/{doc_dir}/README.md", _domain_readme(doc_dir, _domain_title(doc_dir)), force)
        _safe_write(root / f"docs/{doc_dir}/AGENTS.md", _domain_agents(doc_dir), force)

    _safe_write(root / "docs/decisions/_template.md", _adr_template(), force)
    _safe_write(root / "docs/agent-workflow/task-handoff.md", _task_handoff(), force)

    product_source = None
    archived_rel = None
    if product_doc is not None:
        product_doc = product_doc.resolve()
        archived = _copy_source(product_doc, root / "docs/product/core/source", force)
        archived_rel = archived.relative_to(root).as_posix()
        prd = _read_product_as_markdown(product_doc, archived_rel)
        _safe_write(root / "docs/product/core/PRD.md", prd, force)
        product_source = str(product_doc)
    else:
        _safe_write(
            root / "docs/product/core/PRD.md",
            "# Product Requirements Document\n\n"
            "No source product document was provided during bootstrap.\n",
            force,
        )

    merge_state(
        root,
        phase="initialized",
        profile=profile,
        project_name=project_name,
        product_source=product_source,
        archived_product=archived_rel,
        generated_by="docs-as-code workflow pack",
    )


def _domain_title(name: str) -> str:
    return {
        "product": "产品需求、原始 PRD、结构化章节与验收基线",
        "architecture": "系统架构、质量属性、部署与跨模块约束",
        "ui": "UI 信息架构、交互规格与设计资产",
        "api": "API 契约、错误码与 OpenAPI 对齐",
        "backend": "后端模块设计与数据模型",
        "frontend": "前端模块设计与 API 消费",
        "tests": "测试策略、验收矩阵与质量基线",
        "decisions": "架构决策记录 ADR",
        "development": "Roadmap、任务板与交付进度",
        "agent-workflow": "Agent 任务交接、DoD 与技能路由",
    }[name]


def _docs_readme() -> str:
    rows = "\n".join(f"- `{name}/` - {_domain_title(name)}" for name in DOC_DIRS)
    return (
        "# docs\n\n"
        "Documentation is managed as code. Domain directories are listed below.\n\n"
        f"{rows}\n\n"
        "Core cross-domain files:\n\n"
        "- `unresolved.md` - open questions and stop-the-line items\n"
        "- `glossary.md` - repository-wide terminology map\n"
    )


def _docs_agents() -> str:
    rows = "\n".join(f"- `docs/{name}/` - {_domain_title(name)}" for name in DOC_DIRS)
    return (
        "# docs/AGENTS.md\n\n"
        "> Scope: `docs/` and all documentation subdirectories.\n\n"
        "## Registered Directories\n\n"
        f"{rows}\n\n"
        "## Rules\n\n"
        "- Every non-empty top-level docs directory must have `README.md` and `AGENTS.md`.\n"
        "- Do not create unregistered docs directories.\n"
        "- Remove any reserved marker once a directory contains real content.\n"
        "- Keep links relative and stable.\n"
        "- When documents conflict, follow repository source-of-truth priority in root `AGENTS.md`.\n"
    )


def _domain_readme(name: str, title: str) -> str:
    return f"# docs/{name}\n\n{title}。\n\n> Governance: `AGENTS.md`.\n"


def _domain_agents(name: str) -> str:
    return (
        f"# docs/{name}/AGENTS.md\n\n"
        f"> Scope: `docs/{name}/`.\n\n"
        "## Rules\n\n"
        "- Keep this directory focused on its declared domain.\n"
        "- Update `README.md` when adding or renaming documents.\n"
        "- Link back to upstream source documents instead of copying large sections.\n"
    )


def _product_meta() -> str:
    return (
        "# Product Meta\n\n"
        "> Derived from `PRD.md`. Keep this file as a navigation and summary layer only.\n\n"
        "## Product Positioning\n\n"
        "- Source document: `PRD.md`\n"
        "- Current status: imported, pending structured review\n\n"
        "## Chapter Map\n\n"
        "Add chapter links after product structuring.\n"
    )


def _unresolved() -> str:
    return (
        "# Unresolved Items\n\n"
        "Agent must stop and ask when implementation touches an open item here.\n\n"
        "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
    )


def _glossary() -> str:
    return (
        "# Glossary\n\n"
        "This file maps cross-domain terms. Definitions live in their upstream source documents.\n\n"
        "| Term | Meaning | Source |\n"
        "| --- | --- | --- |\n"
    )


def _adr_template() -> str:
    return (
        "# ADR-NNN: Title\n\n"
        "- Status: proposed\n"
        "- Date: YYYY-MM-DD\n"
        "- Related modules: TBD\n\n"
        "## Context\n\n"
        "## Decision\n\n"
        "## Consequences\n\n"
        "## References\n"
    )


def _task_handoff() -> str:
    return (
        "# Agent Task Handoff\n\n"
        "## Task Goal\n\n"
        "## Related Specs\n\n"
        "- Product:\n"
        "- API:\n"
        "- Architecture:\n"
        "- Acceptance:\n\n"
        "## Definition of Done\n\n"
        "- Code and tests are complete.\n"
        "- Documentation is synchronized.\n"
        "- Verification commands pass and output is recorded.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a governance-ready docs-as-code repository.")
    parser.add_argument("--target", default=".", help="Target repository directory.")
    parser.add_argument("--product", help="Path to the source product document.")
    parser.add_argument("--profile", default="unknown", help="Target project profile, for example web-app.")
    parser.add_argument("--project-name", default="Project Workspace", help="Project name for generated root README.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files.")
    args = parser.parse_args()
    product = Path(args.product) if args.product else None
    bootstrap(Path(args.target), product, force=args.force, profile=args.profile, project_name=args.project_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
