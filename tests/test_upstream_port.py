"""Upstream fixes exercised together with UsoParser's delivery conventions."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from render_test_support import ResolvedPathTask

from nonebot_plugin_usoparser.config import Config, parse_media_speedup_rules
from nonebot_plugin_usoparser.constants import PlatformEnum, QQ_HEADER
from nonebot_plugin_usoparser.creator import Creator
from nonebot_plugin_usoparser.data import AudioContent, Author, ParseResult, Platform
from nonebot_plugin_usoparser.exception import ParseException
from nonebot_plugin_usoparser.parsers import load_enabled_parsers
from nonebot_plugin_usoparser.parsers.qqmusic import QQMusicParser
from nonebot_plugin_usoparser.parsers.rednote import RedNoteParser
from nonebot_plugin_usoparser.parsers.rednote import discovery
from nonebot_plugin_usoparser.render import Renderer
from nonebot_plugin_usoparser.utils.ffmpeg import FFmpeg


@pytest.mark.asyncio
async def test_rednote_shortlink_uses_qq_headers(monkeypatch):
    parser = RedNoteParser()
    redirect = AsyncMock(return_value=object())
    monkeypatch.setattr(parser, "parse_with_redirect", redirect)
    try:
        keyword, searched = parser.search_url("https://xhslink.com/a/Example")
        await parser.parse(keyword, searched)
        assert redirect.await_args.args == (
            "https://xhslink.com/a/Example", QQ_HEADER,
        )
    finally:
        await parser.aclose()


def note_payload():
    return {
        "title": "测试笔记", "desc": "正文", "lastUpdateTime": 1_700_000_000_000,
        "user": {"nickName": "作者", "avatar": "", "userId": "user1"},
        "interactInfo": {
            "likedCount": "1", "collectedCount": "2",
            "commentCount": "0", "shareCount": "3",
        },
        "cover": {"fileId": "cover"}, "imageList": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("has_note", [False, True])
async def test_rednote_page_access_and_missing_data_diagnostics(monkeypatch, has_note):
    parser = RedNoteParser()
    state = {"noteData": {"data": {"noteData": note_payload()}}}
    html = (
        f"<script>window.__INITIAL_STATE__={json.dumps(state)}</script>"
        if has_note else "<html>需要登录</html>"
    )
    get = AsyncMock(return_value=httpx.Response(
        200, text=html, request=httpx.Request("GET", "https://www.xiaohongshu.com/"),
    ))
    monkeypatch.setattr(parser.httpx, "get", get)
    try:
        keyword, searched = parser.search_url(
            "https://www.xiaohongshu.com/explore/abc123?xsec_token=sample"
        )
        if has_note:
            result = await parser.parse(keyword, searched)
            assert result.title == "测试笔记"
            assert result.author.name == "作者"
        else:
            with pytest.raises(ParseException, match="未能获取小红书笔记数据"):
                await parser.parse(keyword, searched)
        assert get.await_args.kwargs["headers"] == QQ_HEADER
    finally:
        await parser.aclose()


def test_rednote_video_uses_alternate_cdn(monkeypatch):
    payload = note_payload()
    payload["video"] = {"capa": {"duration": 8}, "consumer": {"originVideoKey": "video"}}
    detail = discovery.decoder.decode(json.dumps({
        "noteData": {"data": {"noteData": payload}},
    })).noteData.data.noteData
    download = Mock(return_value=object())
    create = Mock(return_value=object())
    monkeypatch.setattr(discovery.DOWNLOADER, "download_video", download)
    monkeypatch.setattr(Creator, "video", create)
    assert len(detail.medias) == 1
    args = download.call_args.kwargs
    assert args["url"] == "https://sns-video-hw.xhscdn.com/video"
    assert args["fallback_urls"] == ["https://sns-video-bd.xhscdn.com/video"]
    assert args["retry_http_statuses"] == {422, 424}


@pytest.mark.asyncio
@pytest.mark.parametrize("url,expected", [
    ("https://y.qq.com/n/ryqq_v2/songDetail/0039MnYb0qxYhV", "0039MnYb0qxYhV"),
    ("https://y.qq.com/n/yqq/song/584161671.html", "584161671"),
    ("https://i.y.qq.com/v8/playsong.html?songmid=0039MnYb0qxYhV", "0039MnYb0qxYhV"),
    ("https://i.y.qq.com/v8/playsong.html?songmid=&songid=584161671", "584161671"),
])
async def test_qqmusic_variants_dispatch_correctly(monkeypatch, url, expected):
    parser = QQMusicParser()
    parse = AsyncMock(return_value=object())
    monkeypatch.setattr(parser, "_parse_qqmusic", parse)
    try:
        keyword, searched = parser.search_url(url)
        await parser.parse(keyword, searched)
        parse.assert_awaited_once_with(expected)
    finally:
        await parser.aclose()


@pytest.mark.asyncio
async def test_music_sends_original_audio_and_lyrics_files_without_voice(monkeypatch, tmp_path):
    original = tmp_path / "original.flac"
    original.write_bytes(b"flac")
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"mp3")
    audio = AudioContent(path_task=ResolvedPathTask(voice), source=ResolvedPathTask(original))
    result = ParseResult(
        platform=Platform(PlatformEnum.QQMUSIC, "QQ音乐"),
        author=Author("歌手"), url="https://y.qq.com/n/yqq/song/123",
        title="歌曲", content=[audio], extra={"lyric": "[00:01.00]歌词"},
    )
    from nonebot_plugin_usoparser.helper import UniHelper
    from nonebot_plugin_alconna.uniseg import File

    async def file_seg(path, display_name=None):
        return File(path=str(path), name=display_name)

    monkeypatch.setattr(UniHelper, "file_seg", file_seg)
    packets = [packet async for packet in Renderer().send_content(result)]
    assert len(packets) == 2
    assert all(len(packet) == 1 and isinstance(packet[0], File) for packet in packets)
    assert packets[0][0].name.endswith(".lrc")
    assert packets[1][0].name.endswith(".flac")
    assert Path(packets[1][0].path) == original


@pytest.mark.asyncio
async def test_explicit_audio_speedup_keeps_cached_original(monkeypatch, tmp_path):
    original = tmp_path / "original.flac"
    original.write_bytes(b"source")
    derived = tmp_path / "derived.flac"
    derived.write_bytes(b"processed")
    audio = AudioContent(path_task=ResolvedPathTask(original), source=ResolvedPathTask(original))
    audio.speedup = 1.5
    monkeypatch.setattr(FFmpeg, "is_available", AsyncMock(return_value=True))
    monkeypatch.setattr(FFmpeg, "edit_audio", AsyncMock(return_value=ResolvedPathTask(derived).path))
    assert await audio.get_source_path() == ResolvedPathTask(derived).path
    assert original.read_bytes() == b"source"


@pytest.mark.parametrize("ratio", ["0", "-1", "nan", "inf", "-inf"])
def test_invalid_speedup_rules_fail_at_configuration(ratio):
    with pytest.raises(ValueError):
        parse_media_speedup_rules([f"bilibili:123:{ratio}"])


def test_transcode_concurrency_cannot_deadlock_at_zero():
    with pytest.raises(ValueError):
        Config(plite_media_transcode_concurrency=0)


def test_all_platform_parsers_load():
    assert {parser.platform.name for parser in load_enabled_parsers()} == set(PlatformEnum)
