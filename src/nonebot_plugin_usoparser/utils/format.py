from __future__ import annotations

from collections.abc import Callable, MutableSequence, Sequence
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Final, Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from ..constants import STICKER_CDN
from ..data import ContentItem

DEFAULT_PLACEHOLDER_PATTERN: Final = re.compile(r"\[(?P<name>[^]]+)\]")
HTML_NEWLINE_TAGS: Final = frozenset(
    {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "hr"}
)


def replace_placeholder_to_sticker(
    text: str,
    placeholder_pattern: re.Pattern[str],
    platform: str,
    size_resolver: Callable[[str], Literal["small", "medium"]] | None = None,
) -> list[ContentItem]:
    """
    将包含表情占位符的文本拆分为文本与表情

    :param text: 可能包含表情占位符的原始文本，如 "你好[勤洗手]呀"
    :param placeholder_pattern: 用于匹配占位符的正则，需包含名为 "name" 的分组
    :param platform: 平台标识，用于拼接表情 CDN 路径
    :param size_resolver: 一个接收表情名称并返回 size 字符串的函数，例如
                          lambda name: "small" / "medium"
                          若为 None，则默认使用 "small"
    :return: 由普通文本和 ContentItem 组成的列表，顺序与原字符串一致
    """
    if not placeholder_pattern.search(text):
        return [text]

    # creator 会导入 data，而 data 需要本模块的格式化函数，只能在函数内导入
    from ..creator import Creator

    result: list[ContentItem] = []
    last_pos = 0

    for match in placeholder_pattern.finditer(text):
        start, end = match.span()
        if start > last_pos:
            if plain := text[last_pos:start]:
                result.append(plain)

        if name := match["name"]:
            size = size_resolver(name) if size_resolver is not None else "small"
            result.append(
                Creator.sticker(
                    url=STICKER_CDN.format(platform=platform, name=name),
                    size=size,
                    desc=f"[{name}]",
                )
            )
        elif placeholder_text := text[start:end]:
            result.append(placeholder_text)
        last_pos = end

    # 最后剩余的纯文本
    if last_pos < len(text):
        if tail := text[last_pos:]:
            result.append(tail)

    return result


def is_inside(element: object, ancestor: Tag) -> bool:
    """按节点身份判断包含关系，避免正文与引用文字相同而被误跳过。"""
    return any(parent is ancestor for parent in getattr(element, "parents", ()))


def format_num(num: int | float | str | None) -> str | None:
    """统计数统一用 k/m/b，兼容接口已缩写的千、万、亿、w 等数值。"""
    if num is None:
        return None
    text = str(num).strip()
    matched = re.fullmatch(
        r"([<>≤≥~≈]?)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(千|万|亿|[kKmMbBwW])?\s*(\+?)",
        text.replace(",", "").replace("，", ""),
    )
    if matched is None:
        return text
    prefix, digits, original_unit, suffix = matched.groups()
    multipliers = {
        "": 1, "千": 1000, "k": 1000,
        "万": 10000, "w": 10000,
        "m": 1000000, "亿": 100000000, "b": 1000000000,
    }
    try:
        amount = Decimal(digits) * multipliers[(original_unit or "").lower()]
        units = ((Decimal(1), ""), (Decimal(1000), "k"),
                 (Decimal(1000000), "m"), (Decimal(1000000000), "b"))
        index = max(i for i, (scale, _) in enumerate(units) if i == 0 or abs(amount) >= scale)
        value = amount / units[index][0]
        if index:
            value = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if abs(value) >= 1000 and index < len(units) - 1:
                index += 1
                value = (amount / units[index][0]).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        formatted = format(value, "f")
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return f"{prefix}{formatted}{units[index][1]}{suffix}"
    except (InvalidOperation, OverflowError):
        return text


def append_html_text(
    result: MutableSequence[ContentItem], buffer: Sequence[str]
) -> None:
    """合并连续 HTML 文本，保留正文空白与标签产生的换行"""
    if not buffer:
        return
    if normalized := "".join(buffer).strip():
        result.append(normalized)


def html_to_text(root: BeautifulSoup | Tag | str) -> str:
    """按 HTML 标签语义提取文本，保留文本节点内的空白"""
    parts: list[str] = []
    if isinstance(root, str):
        root = BeautifulSoup(root)
    for element in root.descendants:
        if isinstance(element, Tag):
            if element.name in HTML_NEWLINE_TAGS:
                parts.append("\n")
        elif isinstance(element, NavigableString):
            parts.append(str(element))
    return "".join(parts).strip()


def anchor_text(element: Tag, base_url: str) -> str | None:
    """提取链接的显示文本和链接"""
    if element.find("img"):
        return None
    label = element.get_text(" ", strip=True)
    if not label:
        return None
    href = element.get("href")
    if not isinstance(href, str) or not href:
        return label
    if href.startswith("#"):
        return label

    url = urljoin(base_url, href)
    return f"{label} ({url})"


def replace_anchor_hrefs(root: BeautifulSoup | Tag, base_url: str) -> None:
    """将正文中的链接替换为 ``显示文本 (完整地址)``"""
    for element in root.find_all("a"):
        if text := anchor_text(element, base_url):
            element.replace_with(text)
