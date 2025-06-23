from pydantic import BaseModel
from nonebot import on_command, get_plugin_config
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
)
import httpx
def get_public_ip() -> str:
    try:
        response = httpx.get("https://ipinfo.io/json")
        response.raise_for_status()
        return response.json().get("ip", "Unknown IP")
    except httpx.RequestError as e:
        logger.error(f"Failed to get public IP: {e}")
        return "Error fetching IP"

usage_msg = """"""

class Config(BaseModel):
    ip_superusers: set[str] = set("*")  # 用户ID列表，允许查询公网IP

plugin_config = get_plugin_config(Config)

__plugin_meta__ = PluginMetadata(
    name="ip_query",
    description="IP查询插件",
    usage=usage_msg,
    config=Config,
)

ip_query_matcher = on_command("上传色图", aliases={"ip查询"}, priority=5, block=True)

@ip_query_matcher.handle()
async def handle_ip_query(
    bot: Bot,
    event: MessageEvent
):
    """处理IP查询命令"""
    user_id = str(event.get_user_id())
    if user_id in plugin_config.ip_superusers or "*" in plugin_config.ip_superusers:
        ip_address = get_public_ip()
        await ip_query_matcher.finish(f"明乃的涩图小站是: http://{ip_address}:3000，请前往上传图片")
    else:
        await ip_query_matcher.finish("明乃丢失了色图小站。")