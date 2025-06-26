import time
import asyncio
from typing import List, Optional
from pathlib import Path

import nonebot_plugin_localstore as store
from httpx import AsyncClient
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, Message, GroupMessageEvent

from .config import SETU_PATH, SEND_INTERVAL, REPO_BASE_URL
from .perf_timer import PerfTimer
import random


async def download_pic(
    url: str, proxy: Optional[str] = None, file_mode=False, file_name=""
) -> Optional[Path]:
    headers = {
        "Referer": "https://accounts.pixiv.net/login?lang=zh&source=pc&view_type=page&ref=wwwtop_accounts_index",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36",
    }
    download_timer = PerfTimer.start("Image download")
    image_path = (
        store.get_cache_file("nonebot_plugin_setu_now", file_name)
        if SETU_PATH is None
        else Path(SETU_PATH, file_name)
    )
    client = AsyncClient(proxy=proxy, timeout=5)
    try:
        async with client.stream(
            method="GET", url=url, headers=headers, timeout=15
        ) as response:
            if response.status_code != 200:
                logger.warning(
                    f"Image respond status code error: {response.status_code}"
                )
                raise ValueError(
                    f"Image respond status code error: {response.status_code}"
                )
            with open(image_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
    except Exception:
        logger.warning(f"Image download failed: {url}")
        return None
    finally:
        await client.aclose()
        download_timer.stop()
    logger.info(type(image_path))
    return image_path


async def send_forward_msg(
    bot: Bot,
    event: GroupMessageEvent,
    name: str,
    uin: str,
    msgs: List[Message],
):
    """
    :说明: `send_forward_msg`
    > 发送合并转发消息

    :参数:
      * `bot: Bot`: bot 实例
      * `event: GroupMessageEvent`: 群聊事件
      * `name: str`: 名字
      * `uin: str`: qq号
      * `msgs: List[Message]`: 消息列表
    """

    def to_json(msg: Message):
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    messages = [to_json(msg) for msg in msgs]
    await bot.call_api(
        "send_group_forward_msg", group_id=event.group_id, messages=messages
    )


class SpeedLimiter:
    def __init__(self) -> None:
        self.send_success_time = 0

    def send_success(self) -> None:
        self.send_success_time = time.time()

    async def async_speedlimit(self):
        if (delay_time := time.time() - self.send_success_time) < SEND_INTERVAL:
            delay_time = round(delay_time, 2)
            logger.debug(f"Speed limit: Asyncio sleep {delay_time}s")
            await asyncio.sleep(delay_time)


async def fetch_local_pic():
    client = AsyncClient(timeout=5)
    image_list_url = f"{REPO_BASE_URL}/list_images"
    image_url = f"{REPO_BASE_URL}/original/"
    try:
        response = await client.get(image_list_url)
        if response.status_code != 200:
            logger.warning(
                f"Image list respond status code error: {response.status_code}"
            )
            raise ValueError(
                f"Image list respond status code error: {response.status_code}"
            )
        image_list = response.json()['images']
        random_image_name = random.choice(image_list)
        image_url = image_url + random_image_name
        image_path = await download_pic(
            url=image_url, file_mode=True, file_name=random_image_name
        )
        return image_path
    except Exception as e:
        logger.error(f"Fetch local image failed: {e}")
        return None