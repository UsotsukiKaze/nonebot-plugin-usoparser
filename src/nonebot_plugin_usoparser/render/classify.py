"""为默认卡片选择内容版式，不改变解析器的原始内容。"""

from typing import Literal

from ..data import (
    GraphicContent,
    ImageContent,
    LivePhotoContent,
    ParseResult,
    VideoContent,
)
from .theme import MUSIC_PLATFORMS

CardKind = Literal["music", "video", "gallery", "live", "article"]


def _all_content(result: ParseResult):
    yield from result.content
    if result.repost is not None:
        yield from _all_content(result.repost)


def classify_card(result: ParseResult) -> CardKind:
    """直播优先，实况照片按图文处理，普通视频保持按需详情。"""
    if str(result.platform.name) in MUSIC_PLATFORMS:
        return "music"
    if result.extra.get("content_kind") == "live":
        return "live"
    content = tuple(_all_content(result))
    if any(isinstance(item, VideoContent) for item in content):
        return "video"
    if any(
        isinstance(item, ImageContent | GraphicContent | LivePhotoContent)
        for item in content
    ):
        return "gallery"
    return "article"
