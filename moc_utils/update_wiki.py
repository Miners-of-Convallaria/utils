import multiprocessing
import multiprocessing.pool
import os

import UnityPy
from PIL import Image

from .export.animation import export_animations


def export_image(img: Image.Image, dst: str) -> None:
    fp = dst + ".webp"
    if os.path.exists(fp):
        return
    print(f"Exporting {dst}")
    if img.format == "RGBA":
        alpha = img.getchannel("A")
        if all(x == 255 for x in alpha.getdata()):  # type: ignore
            img = img.convert("RGB")

    img.save(fp, quality=95, method=6)


def export_images(
    env: UnityPy.Environment,
    dst: str,
    processing_pool: multiprocessing.pool.Pool,
    tasks: list[multiprocessing.pool.ApplyResult[None]],
) -> None:
    os.makedirs(dst, exist_ok=True)

    sprite_objs = list(filter(lambda obj: obj.type.name == "Sprite", env.objects))
    tex_objs = list(filter(lambda obj: obj.type.name == "Texture2D", env.objects))
    # prefer sprite objects over texture objects, as sprites use the texture objects
    # if there are no sprite objects, use the texture objects instead
    img_objs = sprite_objs if sprite_objs else tex_objs
    for sprite_obj in img_objs:
        try:
            sprite = sprite_obj.read()  # type: ignore
            img: Image.Image = sprite.image  # type: ignore
            assert isinstance(img, Image.Image)
            img_dst: str = os.path.join(dst, sprite.m_Name)  # type: ignore
            # store the image via a separate process
            if tasks:
                tasks.append(
                    processing_pool.apply_async(
                        export_image,
                        (img, img_dst),
                    )
                )
            else:
                export_image(img, img_dst)
        except ValueError:
            continue
        except Exception as e:
            print(f"Error: {e}")
            print(f"File: {dst}")
            print(f"Object: {sprite_obj.path_id}")
            continue


def update_wiki(dfp: str, ext: str) -> None:
    processing_pool = multiprocessing.Pool(processes=20)
    tasks: list[multiprocessing.pool.ApplyResult[None]] = []

    def load_export_images(fp: str, dst: str) -> None:
        env = UnityPy.load(fp)
        export_images(env, dst, processing_pool, tasks)

    for root, _dirs, files in os.walk(dfp):
        for file in files:
            if file.endswith(".unity3d"):
                fp = os.path.join(root, file)
                rfp = os.path.relpath(fp, dfp)[:-8]

                if rfp.startswith("icon"):
                    # only use the first 2 directories, as the remaining are just split names
                    dst = os.path.join(ext, *rfp.split(os.path.sep)[:2])
                    load_export_images(fp, dst)

                elif rfp.startswith("atlas"):
                    if rfp.endswith("_atlas"):
                        rfp = rfp[:-6]
                    dst = os.path.join(ext, rfp)
                    load_export_images(fp, dst)

                elif rfp.startswith("battle"):
                    split = rfp.split(os.path.sep)
                    match split[1]:
                        case "unit":
                            continue
                        case "map":
                            dst = os.path.join(ext, rfp)
                        case _:
                            dst = os.path.join(ext, "battle", split[1])
                    load_export_images(fp, dst)

                elif rfp == "tmp_sprite_asset":
                    load_export_images(fp, os.path.join(ext, rfp))

    for task in tasks:
        task.wait()
    processing_pool.close()

    # export animations
    fp = os.path.join(dfp, "battle", "unit")
    env = UnityPy.load(fp)
    env.load_folder(os.path.join(dfp, "share"))
    env.load_file(os.path.join(dfp, "shared.unity3d"))
    export_animations(env, os.path.join(ext, "battle", "unit"))


if __name__ == "__main__":
    # dfp = r"D:\Program Files\SwordofConvallaria\SoCLauncher\SwordOfConvallaria\assets"
    dfp = r"D:\Program Files\SwordofConvallaria\SoCLauncher_TW\SwordOfConvallaria\assets"
    ext = r"D:\Projects\SoC\wiki\images"
    update_wiki(dfp, ext)
