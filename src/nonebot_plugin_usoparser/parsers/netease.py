import contextlib
from datetime import datetime, timedelta, timezone
import random
import time
from typing import Any, ClassVar

from nonebot.log import logger

from .base import (
    BaseParser,
    ContentItem,
    MatchWithParams,
    ParseException,
    Platform,
    PlatformEnum,
    handle,
)


def random_ip() -> str:
    return ".".join(str(random.randint(0, 255)) for _ in range(4))


def parse_duration_to_seconds(duration: str) -> int:
    """将时长字符串解析为总秒数"""
    parts = duration.split(":")
    if not (1 <= len(parts) <= 3):
        raise ValueError(f"非法的时长格式: {duration!r}")

    try:
        parts_int = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"时长中包含非法数字: {duration!r}") from exc

    if len(parts_int) == 1:
        hours = 0
        minutes = 0
        seconds = parts_int[0]
    elif len(parts_int) == 2:
        hours = 0
        minutes, seconds = parts_int
    else:
        hours, minutes, seconds = parts_int

    if not (0 <= seconds < 60 and 0 <= minutes < 60 and hours >= 0):
        raise ValueError(f"时长数值不合法: {duration!r}")

    return hours * 3600 + minutes * 60 + seconds


class NCMParser(BaseParser):
    platform: ClassVar[Platform] = Platform(
        name=PlatformEnum.NETEASE, display_name="网易云音乐"
    )

    def __init__(self):
        super().__init__()
        self.httpx.headers.update({"Referer": "https://wyapi.toubiec.cn/"})
        self.httpx.base_url = "https://nextmusic.toubiec.cn/api"

    async def fetch(self, endpoint: str, payload: dict) -> dict:
        payload["timestamp"] = int(time.time() * 1000)
        payload["ip"] = random_ip()
        resp = await self.httpx.post(endpoint, json=payload)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 200:
            raise ParseException(f"接口返回错误: {result}")
        return result["data"]

    async def fetch_catalog(self, song_id: str) -> tuple[str | None, dict[str, str]]:
        """从网易云曲库补充歌手头像与专辑元数据，失败时保留主接口结果。"""
        details: dict[str, str] = {}
        avatar_url = None
        headers = {"Referer": "https://music.163.com/"}
        try:
            response = await self.httpx.get(
                "https://music.163.com/api/song/detail/",
                params={"ids": f"[{song_id}]"},
                headers=headers,
            )
            response.raise_for_status()
            songs = response.json().get("songs") or []
            song = songs[0] if songs else {}
            album = song.get("album") or {}
            if name := album.get("name"):
                details["album"] = str(name)
            if publish_time := album.get("publishTime"):
                details["release_date"] = datetime.fromtimestamp(
                    int(publish_time) / 1000,
                    tz=timezone(timedelta(hours=8)),
                ).strftime("%Y.%m.%d")
            if company := album.get("company"):
                details["record_label"] = str(company)

            artists: list[dict[str, Any]] = song.get("artists") or []
            artist_id = artists[0].get("id") if artists else None
            if artist_id:
                artist_response = await self.httpx.get(
                    f"https://music.163.com/api/artist/{artist_id}",
                    headers=headers,
                )
                artist_response.raise_for_status()
                artist = artist_response.json().get("artist") or {}
                candidate = artist.get("img1v1Url") or artist.get("picUrl")
                if isinstance(candidate, str) and candidate.startswith("https://"):
                    avatar_url = candidate
        except Exception as error:
            logger.warning(f"[网易云解析] 曲库补充信息获取失败: {error}")
        return avatar_url, details

    @handle("163cn.tv", r"https?://[^\s]*?163cn\.tv/[a-zA-Z0-9]+")
    async def _parse_163cn(self, searched: MatchWithParams):
        return await self.parse_with_redirect(searched[0])

    @handle("music.163.com", params={"id": {"as_int": True}})
    @handle("music.163.com", r"song/(?P<id>\d+)")
    async def _parse_netease(self, searched: MatchWithParams):
        ncm_id = searched["id"]
        song = await self.fetch("getSongInfo", {"id": ncm_id})
        avatar_url, catalog = await self.fetch_catalog(str(ncm_id))
        title = song.get("name", "未知")
        artist = song.get("singer", "未知歌手")
        duration = parse_duration_to_seconds(song.get("duration", "0"))
        lyric = ""
        with contextlib.suppress(Exception):
            lyric = (await self.fetch("getSongLyric", {"id": ncm_id})).get("lrc")
        audio_url: str | None = None
        for level in ("lossless", "standard"):
            try:
                url_data = await self.fetch(
                    "getSongUrl", {"id": ncm_id, "level": level}
                )
                audio_url = url_data.get("url")
                if audio_url:
                    break
            except Exception as e:
                logger.warning(f"[网易云解析] {level} 获取失败: {e}")
        if not audio_url:
            raise ParseException("无法获取音频下载地址")
        url_no_params = audio_url.split("?", 1)[0]
        ext = url_no_params.rsplit(".", 1)[-1].lower() if "." in url_no_params else ""
        audio_type = ext if ext in {"flac", "wav", "m4a", "aac", "mp3"} else "mp3"
        contents: list[ContentItem] = []

        audio = self.create_audio(
            audio_url,
            duration=duration,
            cache_key=f"netease:{ncm_id}:{level}",
        )
        contents.append(audio)

        if cover_url := song.get("picimg"):
            contents.append(self.create_image(cover_url))

        audio_info = (
            f"音质: {level} | 大小: {await audio.get_display_size()} |"
            f" 格式: {audio_type}"
        )

        extra = {
            "info": audio_info,
            "lyric": lyric,
            "album": catalog.get("album") or song.get("album") or "",
            "release_date": catalog.get("release_date", ""),
            "record_label": catalog.get("record_label", ""),
        }

        return self.result(
            title=title,
            author=self.create_author(
                name=artist,
                avatar_url=avatar_url,
                ext_headers={"Referer": "https://music.163.com/"},
            ),
            url=f"https://music.163.com/song/{ncm_id}",
            content=contents,
            extra=extra,
        )
