"""Small offline checks for the standalone distribution."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import nonebot


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PackageTests(unittest.TestCase):
    def test_nonebot_plugin_loads_without_ubot_manager(self) -> None:
        nonebot.init()
        plugin = nonebot.load_plugin("nonebot_plugin_usoparser")
        self.assertIsNotNone(plugin)
        self.assertIsNotNone(plugin.metadata)
        self.assertEqual(plugin.metadata.name, "UsoParser")

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
