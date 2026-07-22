from __future__ import annotations

import importlib.util
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = Path(__file__).resolve().parent
PACKAGING_MODULE_PATH = ROOT / "docs_as_code/packaging.py"
PACKAGING_SPEC = importlib.util.spec_from_file_location("docs_as_code_build_packaging", PACKAGING_MODULE_PATH)
if PACKAGING_SPEC is None or PACKAGING_SPEC.loader is None:
    raise RuntimeError(f"unable to load build helper: {PACKAGING_MODULE_PATH}")
PACKAGING_MODULE = importlib.util.module_from_spec(PACKAGING_SPEC)
PACKAGING_SPEC.loader.exec_module(PACKAGING_MODULE)
build_embedded_pack = PACKAGING_MODULE.build_embedded_pack


class build_py(_build_py):
    def run(self) -> None:
        super().run()
        destination = Path(self.build_lib) / "docs_as_code" / "pack"
        build_embedded_pack(ROOT, destination)

    def get_outputs(self, include_bytecode: bool = True) -> list[str]:
        outputs = list(super().get_outputs(include_bytecode=include_bytecode))
        destination = Path(self.build_lib) / "docs_as_code" / "pack"
        if destination.is_dir():
            outputs.extend(str(path) for path in destination.rglob("*") if path.is_file())
        return outputs


setup(cmdclass={"build_py": build_py})
