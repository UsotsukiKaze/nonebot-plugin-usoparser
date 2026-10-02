from __future__ import annotations

import base64
import asyncio
from collections.abc import Callable, Mapping
import contextlib
from datetime import datetime
from html import escape
import inspect
from io import BytesIO
import time
from typing import Any, TypedDict, cast

from anyio import Path
from nonebot import logger
from PIL import Image, ImageOps
import qrcode

from ..data import (
    AudioContent,
    Author,
    Comment,
    ContentItem,
    GraphicContent,
    ImageContent,
    LinkContent,
    LivePhotoContent,
    MediaContent,
    ParseResult,
    PollContent,
    QuoteContent,
    Stats,
    StickerContent,
    VideoContent,
)
from ..download import DOWNLOADER
from .brand import platform_brand_data
from .classify import classify_card
from .theme import MUSIC_PLATFORMS, THEME_SCHEMA_VERSION

PLACEHOLDER_IMAGE = (
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


class ThemeData(TypedDict):
    """Theme API v1 的根数据结构"""

    schema_version: int
    theme: str
    theme_id: str
    post: dict[str, Any]
    meta: dict[str, Any]


async def safe_src(
    obj: Any,
    method: str = "get_path",
    *,
    return_none_on_fail: bool = False,
) -> str | None:
    """把模型对象的资源方法解析成浏览器可用的 URI。

    该函数只供数据转换层使用。主题模板拿到的已经是 URI，不再接触
    Python 模型或异步方法。
    """
    fallback = None if return_none_on_fail else PLACEHOLDER_IMAGE
    try:
        if obj is None or not hasattr(obj, method):
            return fallback
        attr = getattr(obj, method)
        if not callable(attr):
            return fallback
        result = cast(Any, attr)()
        value = await result if inspect.isawaitable(result) else result
        return fallback if value is None else await _path_to_uri(value)
    except Exception as error:
        logger.warning(
            f"safe_src({method}) 处理 {type(obj).__name__} 时失败: {error!r}"
        )
        return fallback


async def build_theme_data(
    result: ParseResult,
    *,
    color_scheme: str,
    theme_id: str,
    bot_name: str,
    max_comments: int,
    append_qrcode: bool,
    include_comments: bool = True,
    include_content: bool = True,
) -> ThemeData:
    """构造主题 API v1 数据。

    返回值只包含 JSON-like 数据：字典、列表、字符串、数字、布尔值和
    ``None``。主题因此不需要知道解析器内部的数据类或资源获取方法
    """
    post = await _serialize_result(
        result,
        theme=color_scheme,
        max_comments=max_comments,
        include_comments=include_comments,
        include_content=include_content,
    )
    if include_content and str(result.platform.name) == "douyin":
        cover_url = result.extra.get("soundtrack_cover_url")
        if isinstance(cover_url, str) and cover_url:
            try:
                cover_path = await asyncio.wait_for(
                    DOWNLOADER.download_img(
                        url=cover_url,
                        cache_key=(
                            f"douyin:music:"
                            f"{result.extra.get('soundtrack_id') or cover_url}"
                        ),
                        cache_variant="cover",
                        ext_headers={"Referer": "https://www.douyin.com/"},
                    ),
                    timeout=8,
                )
                post["extra"]["soundtrack_cover_src"] = await _path_to_uri(
                    cover_path
                )
            except Exception as error:
                logger.debug(f"抖音配乐封面加载失败: {error!r}")
    if (
        append_qrcode
        and post["card_kind"] != "live"
        and str(result.platform.name) not in MUSIC_PLATFORMS
    ):
        post["qrcode"] = _build_qrcode(result.url)

    data: ThemeData = {
        "schema_version": THEME_SCHEMA_VERSION,
        "theme": color_scheme,
        "theme_id": theme_id,
        "post": post,
        "meta": {
            "bot_name": bot_name,
            "rendering_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "width": 620,
        },
    }
    return cast(ThemeData, _escape_html(data))


async def _serialize_result(
    result: ParseResult,
    *,
    theme: str,
    max_comments: int,
    include_comments: bool,
    include_content: bool,
) -> dict[str, Any]:
    is_music = str(result.platform.name) in MUSIC_PLATFORMS

    content: list[dict[str, Any]] = []
    if include_content:
        cover_found = False
        content_jobs = []
        semaphore = asyncio.Semaphore(6)

        async def serialize_item(item: ContentItem, is_cover: bool) -> dict[str, Any]:
            async with semaphore:
                return await _serialize_content(item, is_cover=is_cover)

        for item in result.content:
            is_cover = (
                is_music
                and not cover_found
                and isinstance(item, ImageContent | GraphicContent)
            )
            content_jobs.append(serialize_item(item, is_cover))
            cover_found = cover_found or is_cover
        content = list(await asyncio.gather(*content_jobs))

    return {
        "card_kind": classify_card(result),
        "title": result.title,
        "url": result.url,
        "formatted_datetime": result.formatted_datetime,
        "relative_datetime": _relative_datetime(
            result.timestamp, result.formatted_datetime
        ),
        "live_elapsed": _live_elapsed(result.extra.get("live_started_at")),
        "timestamp": result.timestamp,
        "extra": _json_value(result.extra),
        "platform": platform_brand_data(
            str(result.platform.name), result.platform.display_name, theme
        ),
        "author": await _serialize_author(result.author),
        "content": content,
        "stats": _serialize_stats(result.stats),
        "comments": (
            [
                await _serialize_comment(comment)
                for comment in result.comments[:max_comments]
            ]
            if include_comments
            else []
        ),
        "qrcode": None,
        "ai_summary": result.ai_summary,
        "embed_url": result.embed_url,
        "repost": (
            await _serialize_result(
                result.repost,
                theme=theme,
                max_comments=max_comments,
                include_comments=include_comments,
                include_content=include_content,
            )
            if result.repost
            else None
        ),
    }


def _relative_datetime(timestamp: float | None, fallback: str) -> str:
    try:
        seconds = time.time() - float(timestamp)
    except (TypeError, ValueError, OverflowError, OSError):
        return fallback
    if seconds < 0 or seconds > 30 * 86400:
        return fallback
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"约 {int(seconds // 60)} 分钟前"
    if seconds < 86400:
        return f"约 {int(seconds // 3600)} 小时前"
    return f"约 {int(seconds // 86400)} 天前"


def _live_elapsed(started_at: float | None) -> str:
    try:
        seconds = int(time.time() - float(started_at))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""
    if seconds < 0:
        return ""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}天{hours}小时"
    if hours:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟" if minutes else "不足1分钟"


async def _image_info(obj: Any, method: str = "get_path") -> tuple[bool, str]:
    """检查图片是否可预览，并为直播封面提供横竖屏信息。"""
    try:
        path = await getattr(obj, method)()

        def check() -> tuple[bool, str]:
            with Image.open(str(path)) as image:
                width, height = image.size
            previewable = min(width, height) >= 32 and max(width, height) <= min(width, height) * 12
            return previewable, "portrait" if height > width * 1.1 else "landscape"

        return await asyncio.to_thread(check)
    except Exception as error:
        logger.debug(f"预览图片尺寸检查失败: {error!r}")
        return False, "landscape"


async def _serialize_author(author: Author) -> dict[str, Any]:
    avatar = await safe_src(author, "get_avatar_path", return_none_on_fail=True)
    return {
        "name": author.name,
        "id": author.id,
        "description": author.description,
        "location": author.location,
        "avatar": avatar or PLACEHOLDER_IMAGE,
        "has_avatar": bool(avatar),
    }


async def _serialize_comment(comment: Comment) -> dict[str, Any]:
    return {
        "author": await _serialize_author(comment.author),
        "content": [await _serialize_content(item) for item in comment.content],
        "timestamp": comment.timestamp,
        "formatted_datetime": comment.formatted_datetime,
        "stats": _serialize_stats(comment.stats),
        "replies": [await _serialize_comment(reply) for reply in comment.replies],
        "parent_author": (
            await _serialize_author(comment.parent_author)
            if comment.parent_author
            else None
        ),
    }


def _serialize_stats(stats: Stats) -> dict[str, Any]:
    extra: list[dict[str, Any]] = []
    for key, value in stats.extra.items():
        label, amount = value[0], value[1]
        extra.append(
            {"key": str(key), "label": _json_value(label), "value": _json_value(amount)}
        )
    return {
        "view_count": stats.view_count,
        "like_count": stats.like_count,
        "collect_count": stats.collect_count,
        "share_count": stats.share_count,
        "comment_count": stats.comment_count,
        "extra": extra,
    }


async def _serialize_content(
    item: ContentItem, *, is_cover: bool = False
) -> dict[str, Any]:
    if isinstance(item, str):
        return {"type": "text", "text": item}
    if isinstance(item, ImageContent):
        previewable, orientation = await _image_info(item)
        content = {
            "type": "cover" if is_cover else "image",
            "src": await safe_src(item),
            "layout": item.layout,
            "is_live": False,
            "source_url": _task_url(item),
            "previewable": previewable,
            "orientation": orientation,
        }
        if is_cover:
            content["alt"] = "专辑封面"
        return content
    if isinstance(item, LivePhotoContent):
        previewable, orientation = await _image_info(item, "get_base")
        return {
            "type": "live_photo",
            "src": await safe_src(item, "get_base"),
            "layout": "grid",
            "is_live": True,
            "source_url": _task_url(item),
            "previewable": previewable,
            "orientation": orientation,
        }
    if isinstance(item, GraphicContent):
        previewable, orientation = await _image_info(item)
        content = {
            "type": "cover" if is_cover else "graphic",
            "src": await safe_src(item),
            "alt": item.alt,
            "source_url": _task_url(item),
            "previewable": previewable,
            "orientation": orientation,
        }
        if is_cover:
            content["layout"] = "grid"
            content["is_live"] = False
        return content
    if isinstance(item, StickerContent):
        return {
            "type": "sticker",
            "src": await safe_src(item, return_none_on_fail=True),
            "size": item.size,
            "description": item.desc,
            "source_url": _task_url(item),
        }
    if isinstance(item, VideoContent):
        return {
            "type": "video",
            "src": await safe_src(item, "get_cover_path"),
            "duration": item.display_duration,
            "size": await _display_size(item),
            "source_url": _task_url(item),
        }
    if isinstance(item, AudioContent):
        return {
            "type": "audio",
            "duration": item.display_duration,
            "size": await _display_size(item),
            "source_url": _task_url(item),
        }
    if isinstance(item, LinkContent):
        return {
            "type": "link",
            "url": item.url,
            "title": item.title,
            "site_name": item.site_name,
            "description": item.description,
            "icon": await safe_src(item, "get_icon_path", return_none_on_fail=True),
            "preview": await safe_src(
                item, "get_preview_path", return_none_on_fail=True
            ),
        }
    if isinstance(item, QuoteContent):
        return {
            "type": "quote",
            "text": item.text,
            "title": item.title,
            "url": item.url,
            "icon": await safe_src(item, "get_icon_path", return_none_on_fail=True),
        }
    if isinstance(item, PollContent):
        total = item.option_vote_total
        return {
            "type": "poll",
            "title": item.title,
            "options": [
                {
                    "text": option.text,
                    "votes": option.votes,
                    "percentage": item.option_percentage(option, total),
                    "image": await safe_src(
                        option, "get_image_path", return_none_on_fail=True
                    ),
                }
                for option in item.options
            ],
            "option_vote_total": total,
            "total_votes": item.total_votes,
            "total_voters": item.total_voters,
            "multiple": item.multiple,
            "closed": item.closed,
            "close_at": item.close_at,
            "has_images": any(option.image is not None for option in item.options),
        }
    return {"type": "unknown", "text": str(item)}


async def _display_size(item: MediaContent) -> str:
    try:
        return await item.get_display_size()
    except Exception:
        return "未知大小"


def _task_url(item: MediaContent) -> str | None:
    task = getattr(item, "path_task", None)
    url = getattr(task, "url", None)
    return url if isinstance(url, str) else None


async def _path_to_uri(value: Any) -> str:
    if hasattr(value, "as_uri"):
        with contextlib.suppress(ValueError):
            return cast(Callable[[], str], value.as_uri)()
    return (await Path(str(value)).resolve()).as_uri()


def _build_qrcode(url: str) -> str:
    qr = qrcode.QRCode(version=1, error_correction=1, box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    pixels = qr.make_image(fill_color="black", back_color="white").get_image()
    alpha = ImageOps.invert(pixels.convert("L"))
    image = Image.new("RGBA", pixels.size, (24, 24, 28, 0))
    image.putalpha(alpha)
    buffer = BytesIO()
    image.save(buffer, format="PNG")  # pyright: ignore[reportCallIssue]
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"


def _escape_html(value: Any) -> Any:
    """递归转义传给主题模板的字符串值。"""
    if isinstance(value, str):
        return escape(value, quote=True)
    if isinstance(value, Mapping):
        return {
            escape(key, quote=True) if isinstance(key, str) else key: _escape_html(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [_escape_html(item) for item in value]
    return value


def _json_value(value: Any) -> Any:
    """把扩展字段限制为主题可以安全消费的 JSON-like 值"""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_value(item) for item in value]
    return str(value)
