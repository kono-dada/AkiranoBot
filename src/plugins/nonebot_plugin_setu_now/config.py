from pydantic import BaseModel
from nonebot import get_plugin_config
from typing import Set


class Config(BaseModel):
    superusers: Set[str]
    debug: bool = False
    setu_cd: int = 60
    setu_path: str | None = None
    setu_proxy: str | None = None
    setu_withdraw: int | None = None
    setu_reverse_proxy: str = "i.pixiv.re"
    setu_size: str = "regular"
    setu_api_url: str = "https://api.lolicon.app/setu/v2"
    setu_max: int = 30
    setu_add_random_effect: bool = True
    setu_minimum_send_interval: int = 3
    setu_send_as_bytes: bool = True
    setu_excludeAI: bool = False
    setu_repo_base_url: str = ""


plugin_config = get_plugin_config(Config)
CDTIME = plugin_config.setu_cd
SETU_PATH = plugin_config.setu_path
PROXY = plugin_config.setu_proxy
WITHDRAW_TIME = plugin_config.setu_withdraw
REVERSE_PROXY = plugin_config.setu_reverse_proxy
SETU_SIZE = plugin_config.setu_size
API_URL = plugin_config.setu_api_url
MAX = plugin_config.setu_max
EFFECT = plugin_config.setu_add_random_effect
SEND_INTERVAL = plugin_config.setu_minimum_send_interval
SEND_AS_BYTES = plugin_config.setu_send_as_bytes
EXCLUDEAI = plugin_config.setu_excludeAI
REPO_BASE_URL = plugin_config.setu_repo_base_url