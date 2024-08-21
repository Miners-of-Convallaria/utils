import concurrent
import json
import os
from typing import Any
from typing import Callable
from typing import Optional
from typing import cast

import click

from moc_utils.asset_api import REGION
from moc_utils.asset_api import AssetAPIHandler
from moc_utils.asset_api import AssetMd5Utils
from moc_utils.news import LANGUAGE as NEWS_LANGUAGE
from moc_utils.news import TapSDKBillboard


@click.group("asset")
@click.option("--dst", nargs=1, help="Path to save the files to.", required=True)
@click.option(
    "--cdn",
    nargs=1,
    help="cdn to use (us-prod, tw-prod, jp-prod, cn-prod)",
    required=True,
)
@click.option("--channel", nargs=1, help="channel to use.", required=False)
@click.option("--lang", nargs=1, help="language to use", required=False)
@click.pass_context
def asset(ctx: click.Context, dst: str, cdn: REGION, channel: Optional[REGION], lang: Optional[str]) -> None:
    ctx.ensure_object(dict)
    if channel is None:
        channel = cdn
    ctx.obj["DST"] = dst
    ctx.obj["HANDLER"] = AssetAPIHandler.fetch(cdn, channel)
    ctx.obj["LANGUAGE"] = lang


def download_n_store(func: Callable[..., bytes], values: list[Any], dst: str) -> None:
    data = func(*values)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(data)


@asset.command("download-game", help="Download the game files (not assets).")
@click.pass_context
def download_game(ctx: click.Context) -> None:
    handler: AssetAPIHandler = ctx.obj["HANDLER"]
    dst = ctx.obj["DST"]

    file_infos = handler.get_gamefileinfo_win()

    thread_pool = concurrent.futures.ThreadPoolExecutor()  # type: ignore
    threads = []

    for file_info in file_infos["FileInfos"]:
        print(f"Starting download of {file_info['FileName']}...")
        fp = os.path.join(dst, file_info["FileName"])
        threads.append(thread_pool.submit(download_n_store, handler.get_gamefile_pc, [file_info], fp))  # type: ignore

    concurrent.futures.wait(threads)  # type: ignore
    print("Download complete.")


@asset.command("download-launcher", help="Download the launcher installer.")
@click.pass_context
def download_launcher(ctx: click.Context) -> None:
    handler: AssetAPIHandler = ctx.obj["HANDLER"]
    dst = ctx.obj["DST"]

    os.makedirs(dst, exist_ok=True)
    fp = os.path.join(dst, f"SoCLauncher_PC_{handler.channel}.exe")
    with open(fp, "wb") as f:
        f.write(handler.get_launcher_pc())


@asset.command("download-assets", help="Download the assets.")
@click.pass_context
def download_assets(ctx: click.Context) -> None:
    handler: AssetAPIHandler = ctx.obj["HANDLER"]
    dst = ctx.obj["DST"]

    os.makedirs(dst, exist_ok=True)

    filehash_fp = os.path.join(dst, "file_hash.txt")
    if os.path.exists(filehash_fp):
        with open(filehash_fp, "rt", encoding="utf8") as f:
            filehash_text = f.read()
        local = AssetMd5Utils.parse_hash_file(filehash_text)
    else:
        local = {}

    remote = handler.get_asset_md5()

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

        fp = os.path.join(dst, f"{key}.unity3d")
        threads.append(thread_pool.submit(download_n_store, handler.get_unity_asset, [key, entry["md5"]], fp))  # type: ignore

    concurrent.futures.wait(threads)  # type: ignore
    with open(filehash_fp, "wt", encoding="utf8") as f:
        f.write(AssetMd5Utils.dump_hash_file(remote))
    print("Download complete.")


@asset.command("news-link", help="prints the news link for the given server")
@click.pass_context
def news_link(ctx: click.Context) -> None:
    handler: AssetAPIHandler = ctx.obj["HANDLER"]
    bb = TapSDKBillboard.from_online_handler(handler)
    print(bb.generate_view_url())


@asset.command("news-details", help="stores all current news with their details/content")
@click.pass_context
def news_details(ctx: click.Context) -> None:
    handler: AssetAPIHandler = ctx.obj["HANDLER"]
    bb = TapSDKBillboard.from_online_handler(handler)

    lang: Optional[str] = ctx.obj["LANG"]
    if lang is None:
        if handler.channel.startswith("us"):
            lang = "en_US"
        elif handler.channel.startswith("tw"):
            lang = "zh_TW"
        elif handler.channel.startswith("jp"):
            lang = "ja_JP"
        elif handler.channel.startswith("cn"):
            lang = "zh_CN"

    if lang is None or (not lang and NEWS_LANGUAGE):
        print(f"Invalid language - {lang}!")
        print(f"supported are: {NEWS_LANGUAGE}")
        exit(1)

    lang = cast(NEWS_LANGUAGE, lang)
    activity = bb.get_all_announcement_details("activity", lang)
    game = bb.get_all_announcement_details("game", lang)

    dst: str = ctx.obj["DST"]
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, "activity.json"), "wt", encoding="utf8") as f:
        json.dump(activity, f)
    with open(os.path.join(dst, "game.json"), "wt", encoding="utf8") as f:
        json.dump(game, f)


# @click.group("dump-database")
# @click.option("--dst", nargs=1, help="where the database should be exported to", required=True)
# @click.option("--loc", nargs=1, help="localisation to use: none (default), en, ja, ko, zh-cn, zh-tw", required=False)
# @click.option("--area", nargs=1, help="none (default), cn, tw, jp, kr, us")
# @click.pass_context
# def cli_dump_database(ctx: click.Context, dst: str, loc: str = "none", area: str = "none") -> None:
#     ctx.ensure_object(dict)
#     ctx.obj["DST"] = dst
#     ctx.obj["LOC"] = loc
#     ctx.obj["AREA"] = area


# @cli_dump_database.command("local", help="dumps the db from the local game installation")
# @click.pass_context
# @click.argument("game-dir", type=click.Path(exists=True))
# def dump_database_local(ctx: click.Context, game_dir: str) -> None:
#     dump_database(game_dir, ctx.obj["DST"], ctx.obj["LOC"], ctx.obj["AREA"])

if __name__ == "__main__":
    asset()
