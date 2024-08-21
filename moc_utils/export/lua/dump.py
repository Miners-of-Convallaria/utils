import os
from itertools import cycle
from typing import TYPE_CHECKING
from typing import Callable
from typing import Literal
from typing import Optional

import UnityPy

from .handler import LuaHandler

if TYPE_CHECKING:
    from UnityPy.classes import TextAsset

LUA_PATH = os.path.join(os.path.dirname(__file__), "scripts")


def lua_require_unitypy(lua_map: dict[str, bytes]) -> Callable[[str], bytes]:
    def lua_require(filename: str) -> bytes:
        print(f"Py: Loading {filename}")
        if filename in lua_map:
            return lua_map[filename]

        fp = os.path.join(LUA_PATH, f"{filename}.lua")
        if not os.path.exists(fp):
            dirname, name = filename.split("/", 1)
            key = f"{dirname.lower()}/{name}"
            return lua_map.get(key, b"")

        with open(fp, "rb") as f:
            return f.read()

    return lua_require


# class LuaIOHandler:
#     files: dict[str, bytes]

#     def __init__(self) -> None:
#         self.files = {}

#     def open(self, filename: str, mode: str) -> None:
#         if mode.startswith("w"):
#             self.files[filename] = io.BytesIO()
#         elif mode.startswith("r"):
#             # TODO
#             pass
#         else:
#             raise ValueError(f"Unimplemented mode: {mode}")

#         return filename


def dump_database(
    game_dir: str,
    dst_dir: str,
    loc: str = "none",
    operating_area: Literal["none", "cn", "tw", "jp", "kr", "us"] = "none",
    slua_fp: Optional[str] = None,
) -> None:
    if slua_fp is None:
        slua_fp = os.path.join(game_dir, "SoC_Data", "Plugins", "x86_64", "slua.dll")
    assets_fp = os.path.join(game_dir, "assets")

    lua_map: dict[str, bytes] = {}
    unity_lua_dir = os.path.join(assets_fp, "lua")
    for file in os.listdir(unity_lua_dir):
        env = UnityPy.load(os.path.join(unity_lua_dir, file))  # type: ignore
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                ta: TextAsset = obj.read()  # type: ignore
                key = f"{file[4:-8]}/{ta.m_Name}"
                lua_map[key] = bytes(decrypt_textasset_data(ta.m_Script))  # type: ignore

    os.makedirs(dst_dir, exist_ok=True)
    dst_dir_lua = dst_dir.replace("\\", "\\\\")
    asset_dir_lua = assets_fp.replace("\\", "\\\\")
    dump_code_init = f"""
    Localization = "{loc}"
    OperatingArea = "{operating_area}"
    EXPORT_DIR = "{dst_dir_lua}"
    ASSET_DIR = "{asset_dir_lua}"
    require("dump")
    """

    handler = LuaHandler(slua_fp)
    handler.register_package_loader(lua_require_unitypy(lua_map))
    handler.loadstring(dump_code_init)
    if handler.pcall(0, 1, 0):
        err_msg = handler.tolstring(-1)
        print("Error executing Lua script:", err_msg)


def decrypt_textasset_data(enc: bytes) -> bytearray:
    dec_k = bytearray([23, 241, 195, 85, 120, 100, 57, 64, 66, 119, 89, 18, 51, 203, 123, 185, 53])
    return bytearray([enc[0] ^ 53, *[e ^ k for e, k in zip(enc[1:], cycle(dec_k))]])


def extract_scripts(game_fp: str, dst_fp: str, game_lua_fp: Optional[str] = None) -> None:
    if game_lua_fp is None:
        game_lua_fp = os.path.join(game_fp, "assets", "lua")
    unity_asset_fps = [os.path.join(root, file) for root, _dirs, files in os.walk(game_lua_fp) for file in files]
    for i, unity_asset_fp in enumerate(unity_asset_fps):
        print(f"Extracting {i + 1}/{len(unity_asset_fps)}: {unity_asset_fp}")
        name = os.path.basename(unity_asset_fp)
        if name.startswith("lua_"):
            name = name[4:]
        if name.endswith(".unity3d"):
            name = name[:-8]

        exp_dir = os.path.join(dst_fp, name)
        env = UnityPy.load(unity_asset_fp)  # type: ignore
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            ta: TextAsset = obj.read()  # type: ignore
            print("", ta.m_Name)

            os.makedirs(exp_dir, exist_ok=True)
            with open(os.path.join(exp_dir, f"{ta.m_Name}.lua"), "wb") as f:
                f.write(decrypt_textasset_data(ta.m_Script))  # type: ignore
