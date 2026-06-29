from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .state import STATE_REL, merge_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from state import STATE_REL, merge_state, utc_now


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
    "gates.py",
    "governance_cli.py",
    "phases.py",
    "product_import.py",
    "scaffold.py",
    "state.py",
    "verify_governance.py",
]
RUNTIME_MANIFEST_REL = "docs/agent-workflow/runtime-manifest.json"
MARKDOWN_PRODUCT_SUFFIXES = {".md", ".markdown"}

ROOT_GENERATED_FILES = [
    "README.md",
    "AGENTS.md",
    "SPEC.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "SECURITY.md",
    ".gitignore",
    "Makefile",
]

WORKFLOW_PACK_SNAPSHOT_ROOT = "docs/agent-workflow/workflow-pack"
WORKFLOW_PACK_RESOURCE_PATHS = [
    "README.md",
    "workflows",
    "skills",
    "references",
    "templates",
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


def _runtime_file_paths() -> list[Path]:
    paths = [Path("bin") / name for name in RUNTIME_BIN_FILES]
    paths.extend(Path("scripts") / name for name in RUNTIME_SCRIPT_FILES)
    return sorted(paths, key=lambda path: path.as_posix())


def _write_runtime_manifest(root: Path, force: bool = False) -> str:
    entries = []
    for rel in _runtime_file_paths():
        path = root / rel
        if not path.exists():
            continue
        entries.append(
            {
                "path": rel.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "created_at": utc_now(),
        "source": "target-local governance runtime",
        "files": entries,
    }
    path = root / RUNTIME_MANIFEST_REL
    _write_json(path, manifest, force=True)
    return RUNTIME_MANIFEST_REL


def _source_workflow_pack_root() -> Path:
    pack_root = Path(__file__).resolve().parents[1]
    if all((pack_root / path).exists() for path in ("workflows", "skills", "references")):
        return pack_root
    snapshot = pack_root / WORKFLOW_PACK_SNAPSHOT_ROOT
    if snapshot.exists():
        return snapshot
    return pack_root


def _is_ignored_pack_file(path: Path) -> bool:
    parts = set(path.parts)
    return (
        "__pycache__" in parts
        or ".git" in parts
        or path.suffix == ".pyc"
        or path.name in {".DS_Store", "manifest.json"}
    )


def _iter_workflow_pack_files() -> list[Path]:
    source_root = _source_workflow_pack_root()
    files: list[Path] = []
    for rel in WORKFLOW_PACK_RESOURCE_PATHS:
        source = source_root / rel
        if not source.exists():
            continue
        if source.is_file():
            if not _is_ignored_pack_file(source):
                files.append(Path(rel))
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and not _is_ignored_pack_file(path):
                files.append(path.relative_to(source_root))
    return sorted(files, key=lambda path: path.as_posix())


def _install_workflow_pack_snapshot(root: Path, force: bool = False) -> str:
    source_root = _source_workflow_pack_root()
    snapshot_root = root / WORKFLOW_PACK_SNAPSHOT_ROOT
    copied: list[Path] = []
    for rel in _iter_workflow_pack_files():
        source = source_root / rel
        target = snapshot_root / rel
        _copy_runtime_file(source, target, force)
        copied.append(rel)
    manifest = _workflow_pack_manifest(snapshot_root, copied)
    manifest_path = snapshot_root / "manifest.json"
    _write_json(manifest_path, manifest, force=True)
    return manifest_path.relative_to(root).as_posix()


def _workflow_pack_manifest(snapshot_root: Path, files: list[Path]) -> dict[str, object]:
    entries = []
    for rel in files:
        path = snapshot_root / rel
        if not path.exists():
            continue
        entries.append(
            {
                "path": rel.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema_version": 1,
        "created_at": utc_now(),
        "source": "docs-as-code workflow pack",
        "files": entries,
    }


@dataclass
class InitConflict:
    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "reason": self.reason,
        }


@dataclass
class InitPreflightResult:
    target: str
    ok: bool
    conflicts: list[InitConflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    product: dict[str, object] = field(default_factory=dict)
    would_write: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "warnings": self.warnings,
            "product": self.product,
            "would_write": self.would_write,
        }


class InitPreflightError(RuntimeError):
    def __init__(self, result: InitPreflightResult) -> None:
        super().__init__("initialization preflight failed")
        self.result = result


@dataclass
class RuntimeRefreshResult:
    target: str
    ok: bool
    refreshed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "refreshed": self.refreshed,
            "errors": self.errors,
            "state": self.state,
        }


def generated_file_paths(product_doc: Path | None = None) -> list[str]:
    paths = list(ROOT_GENERATED_FILES)
    paths.extend(f"bin/{name}" for name in RUNTIME_BIN_FILES)
    paths.extend(f"scripts/{name}" for name in RUNTIME_SCRIPT_FILES)
    paths.append(RUNTIME_MANIFEST_REL)
    paths.extend(f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{path.as_posix()}" for path in _iter_workflow_pack_files())
    paths.extend(
        [
            "docs/README.md",
            "docs/AGENTS.md",
            "docs/unresolved.md",
            "docs/glossary.md",
            "docs/product/README.md",
            "docs/product/AGENTS.md",
            "docs/product/core/product-meta.md",
            "docs/product/core/PRD.md",
            "docs/product/core/source/source-manifest.json",
            "docs/decisions/_template.md",
            "docs/agent-workflow/task-handoff.md",
            f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/manifest.json",
            ".governance/state.json",
        ]
    )
    for doc_dir in DOC_DIRS:
        if doc_dir == "product":
            continue
        paths.append(f"docs/{doc_dir}/README.md")
        paths.append(f"docs/{doc_dir}/AGENTS.md")
    if product_doc is not None:
        paths.append(f"docs/product/core/source/{product_doc.name}")
    return sorted(dict.fromkeys(paths))


def preflight_init(root: Path, product_doc: Path | None = None, force: bool = False) -> InitPreflightResult:
    root = root.resolve()
    paths = generated_file_paths(product_doc)
    product = _product_payload(product_doc)
    conflicts: list[InitConflict] = []
    product_resolved = product_doc.resolve() if product_doc is not None and product_doc.exists() else None

    conflicts.extend(_product_preflight_conflicts(product_doc))

    for rel in paths:
        target = root / rel
        if product_resolved is not None and target.resolve() == product_resolved:
            conflicts.append(InitConflict(rel, "product document path overlaps generated output"))
            continue
        if not force and target.exists():
            conflicts.append(InitConflict(rel, "generated file already exists"))

    return InitPreflightResult(
        target=str(root),
        ok=not conflicts,
        conflicts=conflicts,
        product=product,
        would_write=paths,
    )


def _product_preflight_conflicts(product_doc: Path | None) -> list[InitConflict]:
    if product_doc is None:
        return []
    if not product_doc.exists():
        return [InitConflict(str(product_doc), "product document is missing")]
    if not product_doc.is_file():
        return [InitConflict(str(product_doc), "product document is not a file")]
    try:
        if product_doc.suffix.lower() in MARKDOWN_PRODUCT_SUFFIXES:
            product_doc.read_text(encoding="utf-8")
        else:
            with product_doc.open("rb") as handle:
                handle.read(1)
    except UnicodeDecodeError:
        return [InitConflict(str(product_doc), "markdown product document is not valid UTF-8")]
    except OSError as error:
        reason = error.strerror or str(error)
        return [InitConflict(str(product_doc), f"product document is unreadable: {reason}")]
    return []


def refresh_runtime(root: Path) -> RuntimeRefreshResult:
    root = root.resolve()
    if not (root / STATE_REL).exists():
        return RuntimeRefreshResult(
            target=str(root),
            ok=False,
            errors=[f"target is not an initialized governance repository: {STATE_REL.as_posix()} is missing"],
        )
    pack_root = Path(__file__).resolve().parents[1].resolve()
    if pack_root == root:
        return RuntimeRefreshResult(
            target=str(root),
            ok=False,
            errors=[
                "runtime refresh must be run from a trusted source workflow-pack checkout, "
                "not the target-local runtime"
            ],
        )

    refreshed: list[str] = []
    _install_runtime(root, force=True)
    refreshed.extend(path.as_posix() for path in _runtime_file_paths())
    runtime_manifest = _write_runtime_manifest(root, force=True)
    refreshed.append(runtime_manifest)

    workflow_pack_files = _iter_workflow_pack_files()
    workflow_pack_manifest = _install_workflow_pack_snapshot(root, force=True)
    refreshed.extend(f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{path.as_posix()}" for path in workflow_pack_files)
    refreshed.append(workflow_pack_manifest)
    refreshed = sorted(dict.fromkeys(refreshed))

    state = merge_state(
        root,
        runtime_manifest=runtime_manifest,
        workflow_pack_manifest=workflow_pack_manifest,
        runtime_refreshed_at=utc_now(),
    )
    return RuntimeRefreshResult(
        target=str(root),
        ok=True,
        refreshed=refreshed,
        state=state,
    )


def _product_payload(product_doc: Path | None) -> dict[str, object]:
    if product_doc is None:
        return {
            "provided": False,
            "path": None,
            "exists": False,
        }
    return {
        "provided": True,
        "path": str(product_doc),
        "exists": product_doc.exists(),
        "is_file": product_doc.is_file(),
        "suffix": product_doc.suffix.lower(),
    }


def _copy_source(product_doc: Path, source_dir: Path, force: bool = False) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / product_doc.name
    if target.exists() and not force:
        return target
    shutil.copy2(product_doc, target)
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, object], force: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _product_source_manifest(
    product_doc: Path | None,
    archived: Path | None,
    archived_rel: str | None,
) -> dict[str, object]:
    prd_path = "docs/product/core/PRD.md"
    if product_doc is None:
        return {
            "schema_version": 1,
            "created_at": utc_now(),
            "source": {
                "provided": False,
                "filename": None,
                "original_path": None,
                "suffix": None,
                "size_bytes": None,
                "sha256": None,
            },
            "archive": {
                "path": None,
                "size_bytes": None,
                "sha256": None,
            },
            "import": {
                "status": "no_source",
                "conversion_method": "none",
                "prd_path": prd_path,
                "can_derive_design": False,
            },
        }

    is_markdown = product_doc.suffix.lower() in MARKDOWN_PRODUCT_SUFFIXES
    status = "ready_for_structuring" if is_markdown else "conversion_required"
    conversion_method = "markdown-copy" if is_markdown else "conversion-required"
    archived_size = archived.stat().st_size if archived else None
    archived_hash = _sha256(archived) if archived else None
    return {
        "schema_version": 1,
        "created_at": utc_now(),
        "source": {
            "provided": True,
            "filename": product_doc.name,
            "original_path": str(product_doc),
            "suffix": product_doc.suffix.lower(),
            "size_bytes": product_doc.stat().st_size,
            "sha256": _sha256(product_doc),
        },
        "archive": {
            "path": archived_rel,
            "size_bytes": archived_size,
            "sha256": archived_hash,
        },
        "import": {
            "status": status,
            "conversion_method": conversion_method,
            "prd_path": prd_path,
            "can_derive_design": is_markdown,
        },
    }


def _read_product_as_markdown(product_doc: Path, archived_rel: str) -> str:
    if product_doc.suffix.lower() in MARKDOWN_PRODUCT_SUFFIXES:
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
    preflight = preflight_init(root, product_doc, force=force)
    if not preflight.ok:
        raise InitPreflightError(preflight)
    root.mkdir(parents=True, exist_ok=True)
    project_name = project_name or "Project Workspace"
    _install_runtime(root, force)
    runtime_manifest = _write_runtime_manifest(root, force)

    _safe_write(
        root / "README.md",
        f"# {project_name}\n\n"
        "This repository was initialized with the docs-as-code governance workflow pack.\n\n"
        "## Start Here\n\n"
        "- Product source: `docs/product/core/PRD.md`\n"
        "- Documentation entry: `docs/README.md`\n"
        "- Governance rules: `AGENTS.md` and `docs/AGENTS.md`\n"
        "- Workflow pack snapshot: `docs/agent-workflow/workflow-pack/`\n"
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
    workflow_pack_manifest = _install_workflow_pack_snapshot(root, force)

    product_source = None
    archived_rel = None
    manifest: dict[str, object]
    if product_doc is not None:
        product_doc = product_doc.resolve()
        archived = _copy_source(product_doc, root / "docs/product/core/source", force)
        archived_rel = archived.relative_to(root).as_posix()
        prd = _read_product_as_markdown(product_doc, archived_rel)
        _safe_write(root / "docs/product/core/PRD.md", prd, force)
        product_source = str(product_doc)
        manifest = _product_source_manifest(product_doc, archived, archived_rel)
    else:
        _safe_write(
            root / "docs/product/core/PRD.md",
            "# Product Requirements Document\n\n"
            "No source product document was provided during bootstrap.\n",
            force,
        )
        manifest = _product_source_manifest(None, None, None)

    _write_json(root / "docs/product/core/source/source-manifest.json", manifest, force=True)
    _safe_write(root / "docs/product/core/product-meta.md", _product_meta(manifest), force=True)
    _append_conversion_unresolved_item(root, manifest)

    merge_state(
        root,
        phase="initialized",
        profile=profile,
        project_name=project_name,
        product_source=product_source,
        archived_product=archived_rel,
        product_import_status=manifest["import"]["status"],
        product_can_derive_design=manifest["import"]["can_derive_design"],
        runtime_manifest=runtime_manifest,
        workflow_pack_manifest=workflow_pack_manifest,
        generated_by="docs-as-code workflow pack",
    )


def _append_conversion_unresolved_item(root: Path, manifest: dict[str, object]) -> None:
    imported = manifest.get("import")
    archive = manifest.get("archive")
    if not isinstance(imported, dict) or not isinstance(archive, dict):
        return
    if imported.get("can_derive_design") is True:
        return
    archived_rel = archive.get("path")
    if not isinstance(archived_rel, str) or not archived_rel:
        return
    path = root / "docs/unresolved.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "| U-001 | Product Archiving |" in text:
        return
    description = f"Convert archived source {archived_rel} to reviewed Markdown PRD before product structuring."
    row = (
        f"| U-001 | Product Archiving | {description} | "
        f"product structuring/design derivation | TBD | {utc_now().split('T', 1)[0]} |\n"
    )
    path.write_text(text.rstrip() + "\n" + row, encoding="utf-8")


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
    if name == "agent-workflow":
        return (
            f"# docs/{name}\n\n"
            f"{title}。\n\n"
            "> Governance: `AGENTS.md`.\n\n"
            "## Index\n\n"
            "- `task-handoff.md` - agent task handoff and completion criteria\n"
            "- `workflow-pack/` - local workflow, skill, reference, and template snapshot\n"
        )
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


def _product_meta(manifest: dict[str, object] | None = None) -> str:
    if manifest:
        source = manifest["source"]
        archive = manifest["archive"]
        imported = manifest["import"]
        can_derive_design = str(imported["can_derive_design"]).lower()
        return (
            "# Product Meta\n\n"
            "> Derived from `PRD.md`. Keep this file as a navigation and summary layer only.\n\n"
            "## Source Archive\n\n"
            f"- Source filename: `{source['filename']}`\n"
            f"- Archived path: `{archive['path']}`\n"
            f"- Source SHA-256: `{source['sha256']}`\n"
            f"- Archive SHA-256: `{archive['sha256']}`\n"
            f"- Conversion method: `{imported['conversion_method']}`\n"
            f"- Import status: `{imported['status']}`\n"
            f"- Can derive design: `{can_derive_design}`\n"
            "- Manifest: `source/source-manifest.json`\n\n"
            "## Product Positioning\n\n"
            "- Current status: imported, pending structured review\n\n"
            "## Chapter Map\n\n"
            "Add chapter links after product structuring.\n"
        )
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
        "`ID` values must use the `U-NNN` unresolved item format, such as `U-001`.\n\n"
        "`Blocking Scope` values other than empty, `-`, `none`, `n/a`, `non-blocking`, or `resolved` block governance verification.\n\n"
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
