import concurrent
import json
import os
from typing import Any
from typing import Callable
from typing import Optional
from typing import cast

import fire

from moc_utils.asset_api import AssetAPIHandler
from moc_utils.asset_api import AssetMd5Utils
from moc_utils.export.lua.dump import dump_database_from_game
from moc_utils.export.lua.dump import dump_database_from_server
from moc_utils.news import LANGUAGE as NEWS_LANGUAGE
from moc_utils.news import TapSDKBillboard


class Downloader(object):
    """
    A downloader for various items available via the cdn of the game.

    Parameters
    ---
    dst: str
        Path to save the files to.
    cdn: str
        cdn to use (us-prod, tw-prod, jp-prod, cn-prod)
    channel: Optional[str]
        channel to use.
    loc: Optional[str]
        localisation to use (None (default), en, ja, ko, zh-cn, zh-tw).
    """

    dst: str
    cdn: str
    channel: str
    loc: Optional[str]
    handler: AssetAPIHandler

    def __init__(self, dst: str, cdn: str, channel: Optional[str] = None, loc: Optional[str] = None) -> None:
        self.dst = dst
        self.cdn = cdn
        self.channel = channel if channel is not None else self.cdn
        self.loc = loc
        self.handler = AssetAPIHandler.fetch(self.cdn, self.channel)  # type: ignore

    def launcher(self) -> None:
        """Downloads the launcher for the game."""
        os.makedirs(self.dst, exist_ok=True)
        fp = os.path.join(self.dst, f"SoCLauncher_PC_{self.channel}.exe")
        with open(fp, "wb") as f:
            f.write(self.handler.get_launcher_pc())

    def game(self) -> None:
        """Downloads the game files for running the game."""
        file_infos = self.handler.get_gamefileinfo_win()

        thread_pool = concurrent.futures.ThreadPoolExecutor()  # type: ignore
        threads = []

        for file_info in file_infos["FileInfos"]:
            print(f"Starting download of {file_info['FileName']}...")
            fp = os.path.join(self.dst, file_info["FileName"])
            threads.append(thread_pool.submit(download_n_store, self.handler.get_gamefile_pc, [file_info], fp))  # type: ignore

        concurrent.futures.wait(threads)  # type: ignore
        print("Download complete.")

    def assets(self) -> None:
        """Downloads the assets for the game."""
        os.makedirs(self.dst, exist_ok=True)

        filehash_fp = os.path.join(self.dst, "file_hash.txt")
        if os.path.exists(filehash_fp):
            with open(filehash_fp, "rt", encoding="utf8") as f:
                filehash_text = f.read()
            local = AssetMd5Utils.parse_hash_file(filehash_text)
        else:
            local = {}

        remote = self.handler.get_asset_md5()

        thread_pool = concurrent.futures.ThreadPoolExecutor()  # type: ignore
        threads = []

        for key, entry in remote.items():
            if key.startswith(("audio", "localization")):
                # TODO
                continue

            if key in local:
                if entry["md5"] == local[key]["md5"]:
                    continue
                print(f"Updating {key}...")
            else:
                print(f"Downloading {key}...")

            fp = os.path.join(self.dst, f"{key}.unity3d")
            threads.append(thread_pool.submit(download_n_store, self.handler.get_unity_asset, [key, entry["md5"]], fp))  # type: ignore

        concurrent.futures.wait(threads)  # type: ignore
        with open(filehash_fp, "wt", encoding="utf8") as f:
            f.write(AssetMd5Utils.dump_hash_file(remote))
        print("Download complete.")


def download_n_store(func: Callable[..., bytes], values: list[Any], dst: str) -> None:
    data = func(*values)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(data)


class News:
    """
    A news fetcher for the game.

    Parameters
    ---
    cdn: str
        cdn to use (us-prod, tw-prod, jp-prod, cn-prod)
    channel: Optional[str]
        channel to use.
    lang: Optional[str]
        language to use (None (default), en_US, zh_TW, ja_JP, zh_CN).
    """

    cdn: str
    channel: str
    lang: Optional[str]
    bb: TapSDKBillboard

    def __init__(self, cdn: str, channel: Optional[str] = None, lang: Optional[str] = None) -> None:
        self.cdn = cdn
        self.channel = channel if channel is not None else self.cdn
        if lang is None:
            if self.channel.startswith("us"):
                lang = "en_US"
            elif self.channel.startswith("tw"):
                lang = "zh_TW"
            elif self.channel.startswith("jp"):
                lang = "ja_JP"
            elif self.channel.startswith("cn"):
                lang = "zh_CN"
        self.lang = lang
        self.bb = TapSDKBillboard.from_online(cdn, channel)  # type: ignore

    def link(self) -> str:
        """Returns the link to the news."""
        return self.bb.generate_view_url()

    def download_details(self, dst: str) -> None:
        """Downloads the news details."""
        if self.lang is None or (not self.lang and NEWS_LANGUAGE):
            print(f"Invalid language - {self.lang}!")
            print(f"supported are: {NEWS_LANGUAGE}")
            exit(1)

        lang = cast(NEWS_LANGUAGE, self.lang)
        activity = self.bb.get_all_announcement_details("activity", lang)
        game = self.bb.get_all_announcement_details("game", lang)

        os.makedirs(dst, exist_ok=True)
        with open(os.path.join(dst, "activity.json"), "wt", encoding="utf8") as f:
            json.dump(activity, f)
        with open(os.path.join(dst, "game.json"), "wt", encoding="utf8") as f:
            json.dump(game, f)


class Database:
    """
    A database dumper for the game.

    Parameters
    ---
    dst: str
        Path to save the files to.
    loc: Optional[str]
        localisation to use (none (default), en, ja, ko, zh-cn, zh-tw).
    area: Optional[str]
        area to use (none (default), us, tw, kr, jp, cn).
    """

    dst: str
    loc: str
    area: str

    def __init__(self, dst: str, loc: str = "none", area: str = "none") -> None:
        self.dst = dst
        self.loc = loc
        self.area = area

    def from_game(self, game_dir: str) -> None:
        """Dumps the database using the game instance."""
        dump_database_from_game(game_dir, self.dst, self.loc, self.area)  # type: ignore

    def from_server(self, cdn: str, channel: Optional[str] = None) -> None:
        """Dumps the database using the assets from the server."""
        handler = AssetAPIHandler.fetch(cdn, channel)  # type: ignore
        dump_database_from_server(handler, self.dst, self.loc, self.area)  # type: ignore


if __name__ == "__main__":
    fire.Fire({"news": News, "download": Downloader, "database": Database})  # type: ignore
