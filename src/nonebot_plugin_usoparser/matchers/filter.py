import asyncio
import json
from typing import Any

from nonebot import get_driver, logger, on_command
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot_plugin_uninfo import ADMIN, Uninfo

from ..config import pconfig

_STATE_PATH = pconfig.data_dir / "parser_state.json"
_LEGACY_DISABLED_GROUPS_PATH = pconfig.data_dir / "disabled_groups.json"
_STATE_LOCK = asyncio.Lock()
_GLOBAL_ENABLED = True
_DISABLED_GROUPS_SET: set[str] = set()


def _group_key(session: Uninfo) -> str | None:
    """返回跨适配器群标识；私聊不生成配置键。"""
    if session.scene.is_private:
        return None
    return f"{session.scope}_{session.scene_path}"


def _decode_state(raw: str) -> tuple[bool, set[str]]:
    payload: Any = json.loads(raw)
    if isinstance(payload, list):
        # 兼容旧版 disabled_groups.json 的纯数组结构。
        return True, {str(item) for item in payload}
    if not isinstance(payload, dict):
        raise ValueError("解析开关状态必须是 JSON 对象")

    global_enabled = payload.get("global_enabled", True)
    disabled_groups = payload.get("disabled_groups", [])
    if not isinstance(global_enabled, bool):
        raise ValueError("global_enabled 必须是布尔值")
    if not isinstance(disabled_groups, list):
        raise ValueError("disabled_groups 必须是数组")
    return global_enabled, {str(item) for item in disabled_groups}


async def _load_state() -> tuple[bool, set[str]]:
    source = _STATE_PATH
    if not await source.exists() and await _LEGACY_DISABLED_GROUPS_PATH.exists():
        source = _LEGACY_DISABLED_GROUPS_PATH
    if not await source.exists():
        return True, set()

    try:
        return _decode_state(await source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        logger.error(f"解析开关状态文件 {source} 损坏，已使用默认开启状态: {e!r}")
        return True, set()


async def _save_state_unlocked() -> None:
    await _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _STATE_PATH.with_suffix(".json.tmp")
    payload = {
        "global_enabled": _GLOBAL_ENABLED,
        "disabled_groups": sorted(_DISABLED_GROUPS_SET),
    }
    try:
        await temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        await temp_path.replace(_STATE_PATH)
    finally:
        await temp_path.unlink(missing_ok=True)


async def save_state() -> None:
    async with _STATE_LOCK:
        await _save_state_unlocked()


@get_driver().on_startup
async def init_parser_state() -> None:
    """加载状态，并将旧版群名单自动迁移到统一状态文件。"""
    global _GLOBAL_ENABLED, _DISABLED_GROUPS_SET
    _GLOBAL_ENABLED, _DISABLED_GROUPS_SET = await _load_state()
    await save_state()


def is_enabled(session: Uninfo) -> bool:
    """解析总开关：用户黑名单 > 全局开关 > 当前群开关。"""
    if f"{session.scope}_{session.user.id}" in pconfig.blacklist_users:
        return False
    if not _GLOBAL_ENABLED:
        return False
    group_key = _group_key(session)
    return group_key is None or group_key not in _DISABLED_GROUPS_SET


async def _set_group_enabled(group_key: str, enabled: bool) -> bool:
    """设置群开关并返回状态是否发生改变。"""
    async with _STATE_LOCK:
        was_enabled = group_key not in _DISABLED_GROUPS_SET
        if was_enabled == enabled:
            return False
        if enabled:
            _DISABLED_GROUPS_SET.remove(group_key)
        else:
            _DISABLED_GROUPS_SET.add(group_key)
        await _save_state_unlocked()
        return True


async def _set_global_enabled(enabled: bool) -> bool:
    """设置全局开关并返回状态是否发生改变。"""
    global _GLOBAL_ENABLED
    async with _STATE_LOCK:
        if _GLOBAL_ENABLED == enabled:
            return False
        _GLOBAL_ENABLED = enabled
        await _save_state_unlocked()
        return True


enable_group_entry = on_command(
    "开启解析", rule=to_me(), permission=SUPERUSER | ADMIN(), block=True
)


@enable_group_entry.handle()
async def enable_group_parser(matcher: Matcher, session: Uninfo) -> None:
    """开启当前群解析；群主、群管理员和超级用户可用。"""
    group_key = _group_key(session)
    if group_key is None:
        await matcher.finish("“开启解析”仅用于群聊；全局开关请使用“全局开启解析”。")
        return

    changed = await _set_group_enabled(group_key, True)
    if not _GLOBAL_ENABLED:
        await matcher.finish(
            "本群解析设置已开启，但当前全局解析仍处于关闭状态，"
            "需要超级用户执行“全局开启解析”后才会实际生效。"
        )
    if changed:
        await matcher.finish("本群链接解析已开启。")
    await matcher.finish("本群链接解析已经开启，无需重复开启。")


disable_group_entry = on_command(
    "关闭解析", rule=to_me(), permission=SUPERUSER | ADMIN(), block=True
)


@disable_group_entry.handle()
async def disable_group_parser(matcher: Matcher, session: Uninfo) -> None:
    """关闭当前群解析；群主、群管理员和超级用户可用。"""
    group_key = _group_key(session)
    if group_key is None:
        await matcher.finish("“关闭解析”仅用于群聊；全局开关请使用“全局关闭解析”。")
        return

    changed = await _set_group_enabled(group_key, False)
    if changed:
        await matcher.finish("本群链接解析已关闭，不影响其他群。")
    await matcher.finish("本群链接解析已经关闭，无需重复关闭。")


enable_global_entry = on_command(
    "全局开启解析", rule=to_me(), permission=SUPERUSER, block=True
)


@enable_global_entry.handle()
async def enable_global_parser(matcher: Matcher) -> None:
    """开启全部群聊及私聊解析；仅超级用户可用。"""
    changed = await _set_global_enabled(True)
    if changed:
        await matcher.finish("全局链接解析已开启，各群将继续按照自己的群级设置运行。")
    await matcher.finish("全局链接解析已经开启，无需重复开启。")


disable_global_entry = on_command(
    "全局关闭解析", rule=to_me(), permission=SUPERUSER, block=True
)


@disable_global_entry.handle()
async def disable_global_parser(matcher: Matcher) -> None:
    """关闭全部群聊及私聊解析；仅超级用户可用。"""
    changed = await _set_global_enabled(False)
    if changed:
        await matcher.finish("全局链接解析已关闭，所有群聊及私聊均停止解析。")
    await matcher.finish("全局链接解析已经关闭，无需重复关闭。")


status_entry = on_command(
    "解析状态", rule=to_me(), permission=SUPERUSER | ADMIN(), block=True
)


@status_entry.handle()
async def show_parser_status(matcher: Matcher, session: Uninfo) -> None:
    """查看全局及当前群的解析状态。"""
    global_text = "开启" if _GLOBAL_ENABLED else "关闭"
    group_key = _group_key(session)
    if group_key is None:
        await matcher.finish(
            f"全局解析：{global_text}\n"
            f"已单独关闭解析的群：{len(_DISABLED_GROUPS_SET)} 个"
        )
        return

    group_enabled = group_key not in _DISABLED_GROUPS_SET
    effective = _GLOBAL_ENABLED and group_enabled
    await matcher.finish(
        f"全局解析：{global_text}\n"
        f"本群解析：{'开启' if group_enabled else '关闭'}\n"
        f"实际状态：{'开启' if effective else '关闭'}"
    )
