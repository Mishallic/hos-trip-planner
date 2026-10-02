"""The domain package must import only the standard library."""

import ast
import sys
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parent.parent / "domain"


def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def test_domain_imports_only_stdlib():
    files = sorted(DOMAIN_DIR.glob("*.py"))
    assert files, "domain package not found"

    offenders = {
        f"{path.name}: {module}"
        for path in files
        for module in imported_top_level_modules(path)
        if module not in sys.stdlib_module_names
    }

    assert not offenders
