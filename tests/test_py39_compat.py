"""Guard the 3.9 floor.

``from __future__ import annotations`` makes ``X | Y`` annotations *parse* on 3.9,
but pydantic and FastAPI evaluate those strings at runtime -- and ``|`` on types
only exists from 3.10. So a stray PEP 604 union imports fine on the dev machine
and explodes on 3.9. This test fails at authoring time instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def _annotations(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and node.annotation:
            yield node.annotation
        elif isinstance(node, ast.arg) and node.annotation:
            yield node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns:
            yield node.returns


def _has_pep604(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) for n in ast.walk(node)
    )


def test_no_pep604_unions_in_annotations():
    """Use Optional[X] / Union[X, Y]; `X | Y` breaks pydantic + FastAPI on 3.9."""
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for ann in _annotations(tree):
            if _has_pep604(ann):
                offenders.append(f"{path.relative_to(SRC)}:{ann.lineno}")
    assert not offenders, (
        "PEP 604 unions found (breaks Python 3.9 at runtime): " + ", ".join(offenders)
    )


def test_sources_compile():
    """Every source file compiles on the interpreter under test.

    Meaningful on the CI matrix's oldest leg: it catches syntax newer than 3.9
    (``match``, ``except*``) that never reaches the annotation check above.
    """
    for path in sorted(SRC.rglob("*.py")):
        compile(path.read_text(), str(path), "exec")


def test_min_version_matches_pyproject():
    """requires-python and the floor these tests enforce must agree."""
    pyproject = (SRC.parent / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.9"' in pyproject
