from nonebot import require

require("nonebot_plugin_localstore")
require("nonebot_plugin_tortoise_orm")
require("coin")

import json
import asyncio
import random
from re import I, sub
from typing import Any, Union, Annotated
from pathlib import Path
import os
import httpx
from PIL import UnidentifiedImageError
from nonebot import on_regex, on_command
from nonebot.log import logger
from nonebot.params import Depends, RegexGroup
from nonebot.plugin import PluginMetadata
from nonebot.exception import ActionFailed
from nonebot.adapters.onebot.v11 import (
    GROUP,
    PRIVATE_FRIEND,
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
    PrivateMessageEvent,
)
from nonebot.adapters.onebot.v11.helpers import (
    Cooldown,
    CooldownIsolateLevel,
    autorevoke_send,
)

from .utils import SpeedLimiter
from .config import MAX, CDTIME, EFFECT, SETU_PATH, WITHDRAW_TIME, Config, EXCLUDEAI, REPO_BASE_URL
from .models import Setu, SetuNotFindError
from .database import SetuInfo, MessageInfo, bind_message_data, auto_update_setuinfo
from .img_utils import EFFECT_FUNC_LIST, image_segment_convert
from .perf_timer import PerfTimer
from .data_source import SetuHandler
from .r18_whitelist import get_group_white_list_record

from ..coin import COIN_MANAGER

from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.internal.matcher import current_event  # 获取当前上下文的事件

original_finish = Matcher.finish

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
Matcher.finish = new_finish


usage_msg = """TL;DR: 色图 或 看文档"""

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-setu-now",
    description="另一个色图插件",
    usage=usage_msg,
    type="application",
    homepage="https://github.com/kexue-z/nonebot-plugin-setu-now",
    config=Config,
    extra={},
)

if SETU_PATH:
    os.makedirs(SETU_PATH, exist_ok=True)

global_speedlimiter = SpeedLimiter()

# TODO: 不要用regex辣
setu_matcher = on_regex(
    r"^(setu|色图|涩图|来点色色|色色|涩涩|来点色图)\s?([x|✖️|×|X|*]?\d+[张|个|份]?)?\s?(r18)?\s?\s?(tag)?\s?(.*)?",
    flags=I,
    permission=PRIVATE_FRIEND | GROUP,
)


@setu_matcher.handle(
    parameterless=[
        Cooldown(
            cooldown=CDTIME,
            prompt="你冲得太快啦，请稍后再试",
            isolate_level=CooldownIsolateLevel.USER,
        )
    ]
)
async def _(
    bot: Bot,
    event: Union[PrivateMessageEvent, GroupMessageEvent],
    # state: T_State,
    regex_group: Annotated[tuple[Any, ...], RegexGroup()],
    white_list_record=Depends(get_group_white_list_record),
):
    random_cost = random.randint(0, 100)
    if COIN_MANAGER.get_balance(str(event.get_user_id())) < random_cost:
        await setu_matcher.finish(
            "你的明乃币不足，无法获取色图喵\n请使用 /c 签到 获取明乃币"
        )
        return
    # await setu_matcher.finish("服务器维护喵，暂停服务抱歉喵")
    setu_total_timer = PerfTimer("Image request total")
    args = list(regex_group)
    logger.debug(f"args={args}")
    num = args[1]
    r18 = args[2]
    tags = args[3]
    key = args[4]

    num = int(sub(r"[张|个|份|x|✖️|×|X|*]", "", num)) if num else 1
    num = min(num, MAX)

    # 如果存在 tag 关键字, 则将 key 视为tag
    if tags:
        tags = list(map(lambda _l: _l.split("或"), key.split()))
        key = ""

    # 仅在私聊中开启
    # r18 = True if (isinstance(event, PrivateMessageEvent) and r18) else False
    if r18:
        if isinstance(event, PrivateMessageEvent):
            r18 = True
        elif isinstance(event, GroupMessageEvent):
            if white_list_record is None:
                await setu_matcher.finish(
                    "不可以涩涩！\n本群未启用R18支持\n请移除R18标签或联系维护组"
                )
            r18 = True

    if r18:
        num = 1

    logger.debug(f"Setu: r18:{r18}, tag:{tags}, key:{key}, num:{num}")

    failure_msg = 0

    async def nb_send_handler(setu: Setu) -> None:
        nonlocal failure_msg, random_cost
        if setu.img is None:
            logger.warning("Invalid image type, skipped")
            failure_msg += 1
            return
        for process_func in EFFECT_FUNC_LIST:
            if r18 and process_func == EFFECT_FUNC_LIST[0]:
                # R18禁止使用默认图像处理方法(do_nothing)
                continue
            # if process_func == EFFECT_FUNC_LIST[0]:
            #     continue
            logger.debug(f"Using effect {process_func}")
            effert_timer = PerfTimer.start("Effect process")
            try:
                image = process_func(setu.img)  # type: ignore
            except UnidentifiedImageError:
                logger.warning(f"Unidentified image: {type(setu.img)}")
                failure_msg += 1
                return
            effert_timer.stop()
            msg = MessageSegment.reply(event.message_id) + Message(image_segment_convert(image)) + MessageSegment.text(f"你花了{random_cost}明乃币得到了色图")
            try:
                await global_speedlimiter.async_speedlimit()
                send_timer = PerfTimer("Image send")
                message_id = 0
                if not WITHDRAW_TIME:
                    # 未设置撤回时间 正常发送
                    message_id: int = (await setu_matcher.send(msg))["message_id"]
                    if not setu.is_local:
                        await auto_update_setuinfo(setu)
                        await bind_message_data(message_id, setu.pid)
                    logger.debug(f"Message ID: {message_id}")
                else:
                    logger.debug(f"Using auto revoke API, interval: {WITHDRAW_TIME}")
                    await autorevoke_send(
                        bot=bot, event=event, message=msg, revoke_interval=WITHDRAW_TIME
                    )
                """
                发送成功
                """
                COIN_MANAGER.modify_coins(str(event.get_user_id()), -random_cost)  # 扣除明乃币
                send_timer.stop()
                global_speedlimiter.send_success()
                if SETU_PATH is None or setu.is_local:  # 未设置缓存路径，删除缓存
                    Path(setu.img).unlink()
                return
            except ActionFailed:
                if not EFFECT:  # 设置不允许添加特效
                    failure_msg += 1
                    return
                await asyncio.sleep(0)
                logger.warning("Image send failed, retrying another effect")
        failure_msg += 1
        logger.warning("Image send failed after tried all effects")
        if SETU_PATH is None:  # 未设置缓存路径，删除缓存
            Path(setu.img).unlink()

    setu_handler = SetuHandler(key, tags, r18, num, nb_send_handler, EXCLUDEAI)
    try:
        await setu_handler.process_request()
    except SetuNotFindError:
        await setu_matcher.finish(f"没有找到关于 {tags or key} 的色图喵")
    if failure_msg:
        await setu_matcher.send(
            message=Message(f"{failure_msg} 张图片消失了喵"),
        )
    setu_total_timer.stop()


setuinfo_matcher = on_command("信息")


@setuinfo_matcher.handle()
async def _(
    event: MessageEvent,
):
    logger.debug("Running setu info handler")
    event_message = event.original_message
    reply_segment = event_message["reply"]

    if reply_segment == []:
        logger.debug("Command invalid: Not specified setu info to get!")
        await setuinfo_matcher.finish("请直接回复需要作品信息的插画")

    reply_segment = reply_segment[0]
    reply_message_id = reply_segment.data["id"]

    logger.debug(f"Get setu info for message id: {reply_message_id}")

    if message_info := await MessageInfo.get_or_none(message_id=reply_message_id):
        message_pid = message_info.pid
    else:
        await setuinfo_matcher.finish("未找到该插画相关信息")

    if setu_info := await SetuInfo.get_or_none(pid=message_pid):
        info_message = MessageSegment.text(f"标题：{setu_info.title}\n")
        info_message += MessageSegment.text(f"画师：{setu_info.author}\n")
        info_message += MessageSegment.text(f"PID：{setu_info.pid}\n")

        # 解析评分信息
        rates = setu_info.rates
        if rates:
            scores = list(rates.values())
            avg_score = sum(scores) / len(scores)
            info_message += MessageSegment.text(f"平均分：{avg_score:.2f}\n")
            info_message += MessageSegment.text("打分记录：\n")
            for uid, score in rates.items():
                info_message += MessageSegment.text(f"{uid}：{score}\n")
        else:
            info_message += MessageSegment.text("暂无评分\n")

        await setu_matcher.finish(MessageSegment.reply(reply_message_id) + info_message)
    else:
        await setuinfo_matcher.finish("该插画相关信息已被移除")


rate_matcher = on_command("评分")

@rate_matcher.handle()
async def _(
    event: MessageEvent,
):
    logger.debug("Running rate handler")
    event_message = event.original_message
    reply_segment = event_message["reply"]

    if reply_segment == []:
        logger.debug("Command invalid: Not specified setu info to rate!")
        await rate_matcher.finish("请直接回复需要评分的插画")

    reply_segment = reply_segment[0]
    reply_message_id = reply_segment.data["id"]

    logger.debug(f"Rate setu for message id: {reply_message_id}")

    # 获取评分内容
    args = event.get_plaintext().strip().split()
    if len(args) < 2 or not args[1].isdigit():
        await rate_matcher.finish("请以“/评分 分数”的格式进行评分，例如 /评分 5")
    rate = int(args[1])
    if not (0 <= rate <= 10):
        await rate_matcher.finish("评分范围为0~10")

    user_id = str(event.get_user_id())

    if message_info := await MessageInfo.get_or_none(message_id=reply_message_id):
        message_pid = message_info.pid
    else:
        await rate_matcher.finish("未找到该插画相关信息")

    if setu_info := await SetuInfo.get_or_none(pid=message_pid):
        # 读取并更新评分字典
        if user_id in setu_info.rates:
            await rate_matcher.finish("你已经打过分了，不要重复评分喵~")
        setu_info.rates[user_id] = rate
        await setu_info.save()
        bonus = random.randint(1, 30)
        COIN_MANAGER.modify_coins(str(event.get_user_id()), bonus)
        await rate_matcher.finish(f"成功评分{rate}分，奖励你{bonus}明乃币喵~")
    else:
        await rate_matcher.finish("该插画相关信息已被移除")


collect_matcher = on_command("收藏")

@collect_matcher.handle()
async def _(
    event: MessageEvent,
):
    logger.debug("Running collect handler")
    event_message = event.original_message
    reply_segment = event_message["reply"]

    if reply_segment == []:
        logger.debug("Command invalid: Not specified setu info to collect!")
        await collect_matcher.finish("请直接回复需要收藏的插画")

    reply_segment = reply_segment[0]
    reply_message_id = reply_segment.data["id"]

    logger.debug(f"Collect setu for message id: {reply_message_id}")

    if message_info := await MessageInfo.get_or_none(message_id=reply_message_id):
        message_pid = message_info.pid
    else:
        await collect_matcher.finish("未找到该插画相关信息")

    if setu_info := await SetuInfo.get_or_none(pid=message_pid):
        pid = setu_info.pid
        filepath = next(Path(SETU_PATH).glob(f"{pid}.*"), None)
        if filepath is None:
            await collect_matcher.finish("未找到该插画文件")
        async with httpx.AsyncClient() as client:
            with open(filepath, "rb") as f:
                files = {'files': (str(filepath), f, 'image/jpeg')}
                response = await client.post(
                    f"{REPO_BASE_URL}/upload",
                    files=files,
                )
        if response.status_code == 200:
            await collect_matcher.finish("已收收录进明乃的涩图站~")
        else:
            await collect_matcher.finish("收录失败，请稍后再试")
    else:
        await collect_matcher.finish("该插画相关信息已被移除")
