from pathlib import Path

import pytest

from ollaborate_studio.workspace import Workspace


def test_workspace_read_search_and_write(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    workspace = Workspace(tmp_path)

    assert workspace.list_files() == ["hello.py"]
    assert workspace.read_file("hello.py") == "print('hello')\n"
    assert workspace.search_files("hello") == ["hello.py:1: print('hello')"]
    assert "Wrote" in workspace.write_file("nested/result.txt", "done")
    assert (tmp_path / "nested/result.txt").read_text() == "done"


def test_workspace_rejects_path_escape(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        workspace.read_file("../secret.txt")

