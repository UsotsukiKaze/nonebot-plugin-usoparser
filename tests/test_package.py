"""Small offline checks for the standalone distribution."""

from __future__ import annotations

import sys
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PackageTests(unittest.TestCase):
    def test_nonebot_plugin_loads_without_ubot_manager(self) -> None:
        # 真实插件加载独立执行，避免其它离线测试的服务替身污染结果。
        result = subprocess.run(
            [sys.executable, "-c", (
                "import sys; sys.path.insert(0, 'src'); import nonebot; "
                "nonebot.init(); plugin = nonebot.load_plugin('nonebot_plugin_usoparser'); "
                "assert plugin is not None; assert plugin.metadata is not None; "
                "assert plugin.metadata.name == 'UsoParser'"
            )],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_packaged_theme_assets_exist(self) -> None:
        base = ROOT / "src" / "nonebot_plugin_usoparser" / "render" / "templates"
        for name in (
            "default.html.jinja",
            "music.html.jinja",
            "showcase.css",
            "music.css",
            "nonebot-logo.png",
            "bilibili-brand-logo.png",
            "ukp.png",
            "platform-marks/douyin-light.svg",
        ):
            with self.subTest(name=name):
                self.assertTrue((base / name).is_file(), name)

    def test_no_ubot_runtime_dependency(self) -> None:
        source = ROOT / "src" / "nonebot_plugin_usoparser"
        self.assertFalse(
            any("ubot_plugin_common" in item.read_text(encoding="utf-8") for item in source.rglob("*.py"))
        )
