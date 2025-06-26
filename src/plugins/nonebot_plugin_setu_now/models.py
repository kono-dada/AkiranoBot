from typing import Dict, List, Optional
from pathlib import Path


from pydantic import BaseModel


class SetuData(BaseModel):
    pid: int
    p: int
    uid: int
    title: str
    author: str
    r18: bool
    width: int
    height: int
    tags: List[str]
    ext: str
    aiType: int
    uploadDate: int
    urls: Dict[str, str]


class SetuApiData(BaseModel):
    error: Optional[str]
    data: List[SetuData]


class Setu:
    def __init__(self, data: SetuData):
        self.title: str = data.title
        self.urls: Dict[str, str] = data.urls
        self.author: str = data.author
        self.tags: List[str] = data.tags
        self.pid: int = data.pid
        self.p: int = data.p
        self.r18: bool = data.r18
        self.ext: str = data.ext
        self.img: Optional[Path] = None
        self.msg: Optional[str] = None
        self.is_local: bool = False

    @staticmethod
    def local_setu(path: Path) -> "Setu":
        """
        Create a Setu instance for a local image.
        """
        setu = Setu(SetuData(pid=0, p=0, uid=0, title="", author="", r18=False,
                             width=0, height=0, tags=[], ext="", aiType=0, uploadDate=0, urls={}))
        setu.img = path
        setu.is_local = True
        return setu


class SetuMessage(BaseModel):
    send: List[str]
    cd: List[str]


class SetuNotFindError(Exception):
    pass
