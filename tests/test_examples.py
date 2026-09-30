"""The examples run against the release and give the answers they describe."""

import os
import runpy
import subprocess
import sys

import duckdb

from district_evolution import core

EXAMPLES = core.PROJECT_ROOT / "examples"


def statements(sql: str) -> list[str]:
    """SQL statements of a script, without comment lines."""
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def test_sql_questions_run_on_the_release(monkeypatch):
    monkeypatch.chdir(core.RELEASE_DIR)  # load.sql reads tables/ relative to the release folder
    db = duckdb.connect()
    for s in statements((core.RELEASE_DIR / "load.sql").read_text()):
        db.execute(s)
    results = [db.execute(q).fetchall() for q in statements((EXAMPLES / "01_questions.sql").read_text())]
    per_map = {r[0]: r[1] for r in results[0]}
    assert (per_map[1951], per_map[2025]) == (316, 742)
    assert [r[1] for r in results[1]] == ["Kangra"] * 9
    assert len(results[2]) == 10 and {"Kannur", "Kozhikode", "Palakkad"} <= {r[0] for r in results[3]} and len(results[4]) > 0


def test_python_examples_run(capsys):
    runpy.run_path(str(EXAMPLES / "02_restate_statistics.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "LINKED" in out and "Hamirpur" in out
    env = {**os.environ, "PYTHONPATH": str(core.PROJECT_ROOT)}
    tree = subprocess.run([sys.executable, str(EXAMPLES / "03_family_tree.py"), "Malabar"], capture_output=True, text=True,
                          env=env, check=True).stdout
    assert "Kozhikode" in tree and "Malabar (IND-000148)" in tree
