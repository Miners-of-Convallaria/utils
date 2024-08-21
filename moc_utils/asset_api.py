import inspect
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Literal
from typing import Optional
from typing import TypedDict

import requests
import UnityPy

REGION = Literal["tw-prod", "us-prod", "kr-prod", "jp-prod"]
AUDIO_LANGUAGE = Literal["cn", "jp", "kr"]


class FileInfo(TypedDict):
    FileName: str
    FileSize: int
    Md5Hash: str


class GameFileInfo(TypedDict):
    FileInfos: list[FileInfo]
    TotalFileSize: int


class AssetMd5Entry(TypedDict):
    md5: str
    size: int


class AssetMd5EntryLocal(TypedDict):
    md5: str
    timestamp: int  # utc, from time of download


AssetMd5 = dict[str, AssetMd5Entry]
AssetMd5Local = dict[str, AssetMd5EntryLocal]


@dataclass
class AssetAPIHandler:
    android_app: str = ""
    android_app_json: str = ""
    android_md5: str = ""
    android_version: str = ""
    debug: bool = False
    enable_voices: str = ""
    gamepad: bool = False
    ios_app: str = ""
    ios_md5: str = ""
    ios_version: str = ""
    launcher_md5: str = ""
    nohash: bool = False
    pc_md5: str = ""
    require_version: str = ""
    tag: str = ""
    tcp: str = ""
    tf: bool = False
    url_asset: str = ""
    user_center: str = ""
    version: str = ""
    win_md5: str = ""
    use_hash: bool = True
    channel: REGION = "us-prod"
    # media
    kcp: str = ""
    no_hash: bool = False
    android_schema: str = ""
    script: str = ""
    Version: str = ""
    template_md5: str = ""

    @classmethod
    def from_dict(cls, env: dict[str, str | bool]) -> "AssetAPIHandler":
        return cls(
            **{
                k: v
                for k, v in env.items()  # type: ignore
                if k in inspect.signature(cls).parameters
            }
        )

    @classmethod
    def fetch(cls, cdn_region: REGION, channel: Optional[REGION] = None, version: str = "0") -> "AssetAPIHandler":
        # server seems to ignore client version, and always return the same response,
        # as long as a client version is provided
        # versions: us-prod, ..., steam-demo -> us-prod
        if channel is None:
            channel = cdn_region
        url = f"https://ssrpg-{cdn_region}-user-center.xdgtw.com/version/{channel}/{version}"
        # print(url)
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        if "RawMap" in data:
            raise ValueError(json.dumps(data))
        return cls.from_dict({**res.json(), channel: channel})

    def get_file(self, directory: str, filename: str) -> bytes:
        url = f"{self.url_asset}{directory}/{filename}"
        res = requests.get(url)
        res.raise_for_status()
        return res.content

    def get_gamefileinfo_win(self) -> GameFileInfo:
        # fetches the list of game files for windows
        # e.g. SoC.exe, UnityPlayer.dll, SoC_Data/app.info, ...
        name = f"GameFileInfo_{self.win_md5}.json" if self.use_hash or not self.win_md5 else "GameFileInfo.json"

        return json.loads(self.get_file("pc", name))

    def get_launcher_pc(self, channel: Optional[REGION] = None, version: Optional[str] = None) -> bytes:
        if channel is None:
            channel = self.channel
        if version is None:
            if not self.launcher_md5:
                raise ValueError("version is required when launcher_md5 is not provided")
            version = self.launcher_md5

        name = f"SoCLauncher_PC_{channel or self.channel}.{version}.exe"

        return self.get_file("Launcher", name)

    def get_gamefile_pc(self, file_info: FileInfo) -> bytes:
        filename = file_info["FileName"]
        if self.use_hash:
            split = filename.rsplit(".", 1)
            if len(split) == 1:
                # name_hash
                filename = f"{split[0]}_{file_info['Md5Hash']}"
            else:
                # name_hash.ext
                filename = f"{split[0]}_{file_info['Md5Hash']}.{split[1]}"

        return self.get_file("pc", filename)

    def get_asset_md5(self) -> AssetMd5:
        # /assets/name -- name - {md5, size} mapping
        asset_md5_unity3d = self.get_unity_asset("asset_md5", self.pc_md5)
        env = UnityPy.load(asset_md5_unity3d)
        asset_md5_ta = next(obj for obj in env.objects if obj.type.name == "TextAsset").read()  # type: ignore
        asset_md5 = json.loads(bytes(asset_md5_ta.m_Script))  # type: ignore
        return asset_md5

    def get_unity_asset(self, asset_name: str, asset_md5: Optional[str] = None) -> bytes:
        name = asset_name
        if self.use_hash:
            assert asset_md5 is not None, "asset_md5 must be provided when use_hash is True"
            name = f"{name}_{asset_md5}"
        return self.get_file("WebAssets", f"{name}.unity3d")

    def get_audio(self, asset_name: str, asset_md5: str) -> bytes:
        name = asset_name
        if self.use_hash:
            name = f"{name}_{asset_md5}.bin"
        return self.get_file("WebAssets", name)


class AssetMd5Utils:
    @staticmethod
    def parse_hash_file(text: str) -> AssetMd5Local:
        return {
            match.group(1): (
                {
                    "md5": match.group(2),
                    "timestamp": int(match.group(3)),
                }
            )
            for match in re.finditer(r"(.+?)\|([a-z0-9]{16})\|(\d+)", text)
        }

    @staticmethod
    def dump_hash_file(asset_md5: AssetMd5) -> str:
        sep = "\n" if os.name == "nt" else "\r\n"
        return sep.join(f"{k}|{v['md5']}|{int(time.time())}" for k, v in asset_md5.items()) + sep

    @staticmethod
    def compare_asset_hashs(asset_md5_local: AssetMd5 | AssetMd5Local, asset_md5_server: AssetMd5) -> AssetMd5:
        """
        Get the difference between the local and server asset hash.
        Returns a dictionary of the asset hash that needs to be downloaded/updated.

        Args:
            asset_md5_local (AssetMd5): The local asset hash.
            asset_md5_server (AssetMd5): The server asset hash.

        Returns:
            AssetMd5: The asset hash that needs to be downloaded/updated.
        """
        return {
            k: v
            for k, v in asset_md5_server.items()
            if k not in asset_md5_local or asset_md5_local[k]["md5"] != v["md5"]
        }
