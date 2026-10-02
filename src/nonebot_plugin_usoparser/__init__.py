from nonebot import logger, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")

from nonebot_plugin_apscheduler import scheduler

from .config import Config
from .matchers import clear_result_cache
from .utils.cache import CacheManager

__plugin_meta__ = PluginMetadata(
    name="UsoParser",
    description="多平台媒体链接解析与卡片渲染",
    usage=(
        "发送支持平台的(BV号/链接/小程序/卡片)即可；"
        "群管理员可使用 开启解析/关闭解析/解析状态，"
        "超级用户可使用 全局开启解析/全局关闭解析"
    ),
    type="application",
    homepage="https://github.com/UsotsukiKaze/nonebot-plugin-usoparser",
    config=Config,
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_alconna", "nonebot_plugin_uninfo"
    ),
    extra={
        "author": "UsotsukiKaze",
        "version": "0.1.0",
        "plugin_type": "NORMAL",
    },
)


@scheduler.scheduled_job("interval", hours=2, id="parser-clean-local-cache")
async def clean_plugin_cache() -> None:
    """周期性清理过期缓存文件，并重置解析状态"""

    try:
        await CacheManager.clean_expired()
    except Exception as e:
        logger.exception(f"清理缓存文件时发生异常: {e!r}")

    clear_result_cache()
