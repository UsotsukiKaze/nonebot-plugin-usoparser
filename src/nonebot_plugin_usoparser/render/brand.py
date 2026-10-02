"""Bundled, background-free platform marks for the default card themes."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

MARKS_DIR = Path(__file__).parent / "templates" / "platform-marks"
WORDMARKS = {
    "acfun": ("AcFun", "#f23b3e", "#ff7778"),
    "qsmusic": ("汽水音乐", "#18c889", "#52e8b4"),
}


@lru_cache(maxsize=1)
def _manifest() -> dict[str, dict[str, Any]]:
    try:
        return json.loads((MARKS_DIR / "marks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def platform_brand_data(platform_id: str, name: str, theme: str) -> dict[str, Any]:
    """Return a local mark; rendering no longer downloads square app icons."""
    data: dict[str, Any] = {"id": platform_id, "name": name}
    if platform_id == "bilibili":
        mark = (MARKS_DIR.parent / "bilibili-brand-logo.png").as_uri()
        data.update(logo=mark, mark=mark, mark_kind="bilibili", mark_width=91)
        return data
    if platform_id == "douyin":
        mark = (MARKS_DIR / f"douyin-{theme}.svg").as_uri()
        data.update(logo=mark, mark=mark, mark_kind="douyin", mark_width=42)
        return data

    spec = _manifest().get(platform_id)
    if spec:
        asset = spec.get(f"{theme}_asset")
        if isinstance(asset, str) and (MARKS_DIR / asset).is_file():
            mark = (MARKS_DIR / asset).as_uri()
            aspect = float(spec.get("aspect", 1))
            data.update(
                logo=mark,
                mark=mark,
                mark_kind="image",
                mark_width=(
                    32
                    if platform_id == "netease"
                    else min(118, max(38, round(42 * aspect)))
                ),
            )
            return data

    label, light, dark = WORDMARKS.get(platform_id, (name, "#252529", "#f6f4f3"))
    data.update(
        logo=None,
        mark=None,
        mark_kind="wordmark",
        mark_text=label,
        mark_color=dark if theme == "dark" else light,
    )
    return data
