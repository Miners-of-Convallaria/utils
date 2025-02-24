import os
import subprocess
from tempfile import NamedTemporaryFile

from .lua_struct_xd import LuaXD

UNLUAC_FP = os.path.join(os.path.dirname(__file__), "resources", "unluac.jar")


def decompile_all(src_fp: str, dst_fp: str) -> None:
    files = [
        os.path.relpath(os.path.join(root, file), src_fp)
        for root, _dirs, files in os.walk(src_fp)
        for file in files
        if file.endswith(".lua")
    ]

    failed = []

    for i, file in enumerate(files):
        print(f"Decompiling {i+1}/{len(files)}: {file}")
        try:
            decompile(os.path.join(src_fp, file), os.path.join(dst_fp, file))
        except Exception as e:
            failed.append(file)
            print(f"Error: {e}")

    if failed:
        print("Failed files:")
        for file in failed:
            print(file)


def decompile(src_fp: str, dst_fp: str) -> None:
    with open(src_fp, "rb") as f:
        lua_xd_raw = f.read()

    lua_xd = LuaXD.from_bytes(lua_xd_raw)
    lua = lua_xd.to_normal()

    ft = NamedTemporaryFile(mode="w+b", suffix=".luac", delete=False)
    ft.write(lua.to_bytes())
    ft.close()

    decompiled = run_unluac(ft.name)

    os.remove(ft.name)

    os.makedirs(os.path.dirname(dst_fp), exist_ok=True)
    with open(dst_fp, "wb") as f:
        f.write(decompiled)


def run_unluac(fp: str) -> str:
    res = subprocess.run(
        ["java", "-Xmx1048m", "-jar", UNLUAC_FP, fp],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if res.returncode != 0:
        raise Exception(f"{fp}\nError: {res.stderr.decode('utf-8')}")
    return res.stdout
