from tortoise import fields
from tortoise.models import Model

from .data_source import SETU_SIZE, Setu
from nonebot_plugin_tortoise_orm import add_model


add_model(__name__)


class SetuInfo(Model):
    pid = fields.IntField(pk=True)
    author = fields.CharField(max_length=50)
    title = fields.CharField(max_length=50)
    url = fields.TextField()
    rates = fields.JSONField(default=dict)  # 用于存储用户评分的JSON

    class Meta:
        table = "setu_info"


async def auto_update_setuinfo(setu_instance: Setu):
    return await SetuInfo.get_or_create(
        pid=int(setu_instance.pid),
        author=setu_instance.author,
        title=setu_instance.title,
        url=setu_instance.urls[SETU_SIZE],
    )


class MessageInfo(Model):
    message_id = fields.IntField(pk=True)
    pid = fields.IntField()

    class Meta:
        table = "message_data"


async def bind_message_data(message_id: int, pid: int):
    return await MessageInfo.get_or_create(
        message_id=message_id,
        pid=pid,
    )


class GroupWhiteListRecord(Model):
    group_id = fields.IntField(pk=True)
    operator_user_id = fields.IntField()

    class Meta:
        table = "white_list"
