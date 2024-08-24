import gc
import os
from itertools import cycle
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from typing import Callable
from typing import Literal
from typing import Optional

import UnityPy
import UnityPy.classes

from .handler import LuaHandler

if TYPE_CHECKING:
    from UnityPy.classes import TextAsset

    from moc_utils.asset_api import AssetAPIHandler

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
    dst: str,
    slua_fp: str,
    asset_dir: str,
    lua_map: dict[str, bytes],
    loc: str = "none",
    operating_area: Literal["none", "cn", "tw", "jp", "kr", "us"] = "none",
) -> None:
    os.makedirs(dst, exist_ok=True)
    dst_dir_lua = dst.replace("\\", "\\\\")
    asset_dir_lua = asset_dir.replace("\\", "\\\\")
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
    del handler


def dump_localization(dst: str, slua_fp: str, lua_map: dict[str, bytes]) -> None:
    os.makedirs(dst, exist_ok=True)
    dst_dir_lua = dst.replace("\\", "\\\\")
    dump_code_init = f"""
    EXPORT_DIR = "{dst_dir_lua}"
    local neatjson = require("neatjson")
    local json_options = {{
        wrap = true,
        sort = function(k) return k end,
    }}
    function export_loc(loc_key)
        local success, func = pcall(loadfile, loc_key)
        if not success or not func then
            return
        end
        local trans_datas = func()
        local loc_table = {{}}
        for index, value in ipairs(trans_datas) do
            local id = value[1]
            local key = value[2]
            local val = value[3]
            if loc_table[id] == nil then
                loc_table[id] = {{}}
            end
            loc_table[id][key] = val
        end
        local string = neatjson(loc_table,  json_options)
        local fp = EXPORT_DIR .. "/" .. loc_key:sub(8) .. ".json"
        local file = io.open(fp, "w")
        file:write(string)
        file:close()
    end
    """
    export_call_template = 'export_loc("{0}")'
    lines = [export_call_template.format(key) for key in lua_map if key.startswith("dblang_")]
    langs = set(key.split("/", 1)[0].split("_", 1)[1] for key in lua_map if key.startswith("dblang_"))
    for lang in langs:
        os.makedirs(os.path.join(dst, lang), exist_ok=True)

    handler = LuaHandler(slua_fp)
    handler.register_package_loader(lua_require_unitypy(lua_map))
    handler.loadstring("\n".join([dump_code_init, *lines]))
    if handler.pcall(0, 1, 0):
        err_msg = handler.tolstring(-1)
        print("Error executing Lua script:", err_msg)

    del handler


def dump_database_n_localization(
    dst: str,
    slua_fp: str,
    asset_dir: str,
    lua_map: dict[str, bytes],
    loc: str = "none",
    operating_area: Literal["none", "cn", "tw", "jp", "kr", "us"] = "none",
) -> None:
    db_dst = os.path.join(dst, "db")

    dump_database(db_dst, slua_fp, asset_dir, lua_map, loc, operating_area)
    dump_localization(dst, slua_fp, lua_map)


def dump_database_from_game(
    game_dir: str,
    dst_dir: str,
    loc: str = "none",
    operating_area: Literal["none", "cn", "tw", "jp", "kr", "us"] = "none",
) -> None:
    slua_fp = os.path.join(game_dir, "SoC_Data", "Plugins", "x86_64", "slua.dll")
    assets_fp = os.path.join(game_dir, "assets")

    print("Loading lua files from assets...")
    lua_map: dict[str, bytes] = {}
    unity_lua_dir = os.path.join(assets_fp, "lua")
    for file in os.listdir(unity_lua_dir):
        lua_dir = file[4:-8]
        if len(lua_dir) > 0:
            lua_dir = f"{lua_dir}/"
        env = UnityPy.load(os.path.join(unity_lua_dir, file))  # type: ignore
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                ta: TextAsset = obj.read()  # type: ignore
                key = f"{lua_dir}{ta.m_Name}"
                lua_map[key] = bytes(decrypt_textasset_data(ta.m_Script))  # type: ignore

    dump_database_n_localization(dst_dir, slua_fp, assets_fp, lua_map, loc, operating_area)


def dump_database_from_server(
    handler: "AssetAPIHandler",
    dst_dir: str,
    loc: str = "none",
    operating_area: Literal["none", "cn", "tw", "jp", "kr", "us"] = "none",
) -> None:
    temp_dir = TemporaryDirectory()
    try:
        print("Fetching game files...")
        # get slua
        gamefile_infos = handler.get_gamefileinfo_win()
        for file_info in gamefile_infos["FileInfos"]:
            if file_info["FileName"].endswith("slua.dll"):
                slua_fp = os.path.join(temp_dir.name, "slua.dll")
                with open(slua_fp, "wb") as f:
                    f.write(handler.get_gamefile_pc(file_info))
                break
        else:
            raise ValueError("slua.dll not found in game files")
        # extract db_lua.bytes
        asset_md5 = handler.get_asset_md5()
        db_template_raw = handler.get_unity_asset("db_template", asset_md5["db_template"]["md5"])
        env = UnityPy.load(db_template_raw)  # type: ignore
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                ta: TextAsset = obj.read()  # type: ignore
                if ta.m_Name == "db_lua":
                    db_lua_bytes = bytes(ta.m_Script)  # type: ignore
                    with open(os.path.join(temp_dir.name, "db_lua.bytes"), "wb") as f:
                        f.write(db_lua_bytes)
                    break
        else:
            raise ValueError("db_lua.bytes not found in db_template")

        # collect all lua files
        print("Loading lua files from directly downloaded assets...")
        lua_map: dict[str, bytes] = {}
        for key, value in asset_md5.items():
            if key.startswith("lua/"):
                lua_dir = key.split("/", 1)[1][4:]
                if len(lua_dir) > 0:
                    lua_dir = f"{lua_dir}/"
                raw = handler.get_unity_asset(key, value["md5"])
                env = UnityPy.load(raw)  # type: ignore
                for obj in env.objects:
                    if obj.type.name == "TextAsset":
                        ta: TextAsset = obj.read()  # type: ignore
                        key = f"{lua_dir}{ta.m_Name}"
                        lua_map[key] = bytes(decrypt_textasset_data(ta.m_Script))  # type: ignore

        dump_database_n_localization(dst_dir, slua_fp, temp_dir.name, lua_map, loc, operating_area)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        gc.collect()
        temp_dir.cleanup()


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
