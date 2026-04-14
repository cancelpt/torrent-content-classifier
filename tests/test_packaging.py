"""Packaging regression tests."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


def test_wheel_includes_default_rules_yaml(tmp_path: Path) -> None:
    """Wheel must include rules/default_rules.yaml for runtime loading."""
    project_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            ".",
            "-w",
            str(wheel_dir),
        ],
        check=True,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    wheels = sorted(wheel_dir.glob("torrent_content_classifier-*.whl"))
    assert wheels, "expected built wheel artifact"

    with zipfile.ZipFile(wheels[-1]) as wheel:
        assert "torrent_content_classifier/rules/default_rules.yaml" in wheel.namelist()
