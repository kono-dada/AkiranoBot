from arclet.alconna import Args, Subcommand, Alconna, Arparma
from nonebot_plugin_alconna import At, on_alconna
from pydantic import BaseModel
from nonebot import get_plugin_config
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import (
    MessageEvent,
)
from .coin_manager import CoinManager
from .exceptions import CoinManagerException, InsufficientFundsException, TransferToSelfException

from nonebot import require
require("nonebot_plugin_alconna")

from nonebot_plugin_alconna.matcher import AlconnaMatcher
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.internal.matcher import current_event  # 获取当前上下文的事件
from nonebot.adapters import Message

original_finish = AlconnaMatcher.finish

# 为 Matcher 重写 finish 方法
@classmethod
async def new_finish(
    cls, 
    message: Message | str | None = None, 
    fallback=True,
    **kwargs
):
    event = current_event.get()
    if hasattr(event, "message_id"):
        reply = MessageSegment.reply(event.message_id)
        message = reply + message
    await original_finish.__func__(cls, message, fallback=fallback, **kwargs)

# 添加方法到 Matcher 实例上
AlconnaMatcher.finish = new_finish


class Config(BaseModel):
    superusers: set[str] = set("*")  # 用户ID列表，允许查询公网IP
    data_file: str = "data/coin/coin_data.json"  # 数据文件路径
    daily_check_in_bonus: int = 500  # 每日签到奖励


plugin_config = get_plugin_config(Config)

__plugin_meta__ = PluginMetadata(
    name="coin",
    description="硬币插件",
    usage="",
    config=Config,
)

COIN_MANAGER = CoinManager(
    data_file=plugin_config.data_file,
    daily_check_in_bonus=plugin_config.daily_check_in_bonus
)

alc = Alconna(
    "/c",
    Subcommand(
        "签到",
    ),
    Subcommand(
        "t",
        Args["target", At | str]["amount", int],
    ),
    Subcommand(
        "q",
        Args["target?", At | str],    # 只有superuser可以查询其他用户余额
        # 如果没有提供target，则查询自己的余额
    ),
    Subcommand(
        "help",
    )
)

coin_cmd = on_alconna(alc, auto_send_output=True)


@coin_cmd.handle()
async def _(result: Arparma, event: MessageEvent):
    # /c 或 /c help
    if not result.main_args and not result.subcommands:
        await coin_cmd.finish(alc.get_help())
    if result.find("签到"):
        try:
            coins = COIN_MANAGER.daily_check_in(str(event.get_user_id()))
        except CoinManagerException as e:
            await coin_cmd.finish("你今天已经签到过了")
        finally:
            await coin_cmd.finish(f"签到成功！当前余额：{coins}")
    if result.find("t"):
        target = result.query("t.target")
        amount = result.query("t.amount")
        if isinstance(target, At):
            target_id = str(target.target)
        else:
            target_id = str(target)
        from_user_id = str(event.get_user_id())
        logger.info(f"转账请求：{from_user_id} -> {target_id} 金额：{amount}")
        try:
            ret = COIN_MANAGER.transfer(from_user_id, target_id, amount)
        except (TransferToSelfException, ValueError):
            COIN_MANAGER.fine(from_user_id, 100)
            await coin_cmd.finish("你在做什么，没收你100明乃币！")
        except InsufficientFundsException:
            await coin_cmd.finish("你没有这么多明乃币！")
        except Exception as e:
            await coin_cmd.finish(f"转账失败：{e}")
        await coin_cmd.finish(f"成功转账{amount}明乃币给{target_id}！\n")
    if result.find("q"):
        target = result.query("q.target")
        logger.info(f"查询余额请求：{target} (请求者: {event.get_user_id()})")
        if isinstance(target, At):
            target_id = str(target.target)
        elif target is None:
            target_id = str(event.get_user_id())
        else:
            target_id = str(target)

        if target_id not in plugin_config.superusers and target_id != str(event.get_user_id()):
            await coin_cmd.finish("你没有权限查询其他用户的余额！")

        balance = COIN_MANAGER.get_balance(target_id)
        await coin_cmd.finish(f"你还有{balance}个明乃币")
    if result.find("help"):
        await coin_cmd.finish(alc.get_help())
    await coin_cmd.finish(alc.get_help())
