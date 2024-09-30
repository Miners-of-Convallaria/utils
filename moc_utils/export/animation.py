import os
from collections import defaultdict
from io import BytesIO

from PIL import Image
import UnityPy
from UnityPy.classes import AnimationClip
from UnityPy.classes import Animator
from UnityPy.classes import AnimatorController
from UnityPy.classes import GameObject
from UnityPy.classes import Material
from UnityPy.classes import PPtr


def normalize_frames(frames: list[Image.Image], offsets: list[tuple[float, float]]) -> list[Image.Image]:
    max_w = 0
    max_h = 0
    for (x, y), frame in zip(offsets, frames):
        w = (frame.width / 2 + x) * 2
        h = (frame.height / 2 + y) * 2

        if w > max_w:
            max_w = w
        if h > max_h:
            max_h = h

    center_w = max_w / 2
    center_h = max_h / 2

    new_frames: list[Image.Image] = []
    for (x, y), frame in zip(offsets, frames):
        new_frame = Image.new("RGBA", (int(max_w), int(max_h)))
        # new_frame.putpalette(frame.getpalette(), rawmode="RGBA")
        # new_frame.info["transparency"] = 0

        off_x = center_w - (frame.width / 2)
        off_y = center_h - (frame.height / 2)
        new_frame.paste(frame.convert("RGBA"), (int(off_x), int(off_y)))
        new_frames.append(new_frame)

    return new_frames


def get_palette(material_pptr: PPtr) -> bytes:
    material: Material = material_pptr.read()
    mat_texs: dict[str, PPtr] = material.m_SavedProperties.m_TexEnvs
    palette_tex_env = next(tex for name, tex in mat_texs if name == "_PaletteTex")
    palette_tex = palette_tex_env.m_Texture.read()
    palette = palette_tex.image.tobytes()
    return palette


def animation_to_gif(anim: AnimationClip, material: PPtr, speedup: int = 1) -> bytes:
    time = anim.m_MuscleClip.m_StopTime - anim.m_MuscleClip.m_StartTime  # type: ignore

    # prepare the processed textures for the sprite handler
    palette = get_palette(material)

    frames: list[Image.Image] = []
    frame_sizes: list[tuple[int, int]] = []
    frame_offsets: list[tuple[float, float]] = []
    for i, frame in enumerate(anim.m_ClipBindingConstant.pptrCurveMapping):
        if frame.path_id == 0:
            continue
        sprite = frame.read()
        raw_image: Image.Image = sprite.image.getchannel(3)

        raw_image.putpalette(palette, rawmode="RGBA")  # type: ignore
        raw_image.info["transparency"] = 0  # type: ignore

        if (
            i == len(anim.m_ClipBindingConstant.pptrCurveMapping) - 1
            and frame.path_id == anim.m_ClipBindingConstant.pptrCurveMapping[0].path_id
        ):
            break
        frames.append(raw_image)
        frame_sizes.append(raw_image.size)
        frame_offsets.append((sprite.m_Offset.x, sprite.m_Offset.x))

    if not frames:
        raise ValueError("No frames to export!")

    if len(set(frame_sizes)) > 1 or len(set(frame_offsets)) > 1:
        # normalize offsets
        min_x = min(x for x, _y in frame_offsets)
        min_y = min(y for _x, y in frame_offsets)
        offsets = [(x - min_x, y - min_y) for x, y in frame_offsets]
        frames = normalize_frames(frames, offsets)

    out_stream = BytesIO()
    frames[0].save(
        out_stream,
        save_all=True,
        append_images=frames[1:],
        duration=time * 1000 / speedup,
        loop=0,
        disposal=2,
        format="GIF",
    )
    return out_stream.getvalue()


def export_gameobject_animations(go: GameObject) -> dict[str, bytes]:
    stack = [go.m_Transform]
    types: defaultdict[str, list[GameObject]] = defaultdict(list)
    while stack:
        transform = stack.pop().read()
        for child in transform.m_Children:
            stack.append(child)
        if not transform.m_GameObject:
            continue
        tgo = transform.m_GameObject.read()
        for component in tgo.m_Components:
            types[component.type.name].append(component)

    animator_controller: AnimatorController
    for animator_ptr in types.get("Animator", []):
        animator: Animator = animator_ptr.read()  # type: ignore
        if animator.m_Controller.path_id != 0:
            animator_controller = animator.m_Controller.read()
            break
    else:
        raise ValueError("No animator controller found!")

    animations: list[AnimationClip] = []
    for anim in animator_controller.m_AnimationClips:
        try:
            anim = anim.read()
        except Exception:
            continue
        animations.append(anim)

    sprite_materials: list[PPtr] = []
    for obj in types["SpriteRenderer"]:
        renderer = obj.read()  # type: ignore
        # sprite_path_id = renderer["m_Sprite"]["m_PathID"]
        material_pptr: int = renderer.m_Materials[0]

        if material_pptr.m_FileID == 0:
            sprite_materials.append(material_pptr)  # type: ignore

    if len(sprite_materials) > 1:
        print(f"Warning: {go.m_Name} has multiple sprite materials")  # type: ignore

    ret: dict[str, bytes] = {}
    for anim in animations:
        try:
            gif = animation_to_gif(anim, sprite_materials[0])
            ret[f"{anim.m_Name}.gif"] = gif
        except Exception:
            pass

    return ret


def export_animations(env: UnityPy.Environment, dst: str) -> None:
    if UnityPy.__version__ < "1.20.0":
        raise ImportError("UnityPy version must be at least 1.20.0")

    root_nodes: dict[int, GameObject] = {}
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        go: GameObject = obj.read()  # type: ignore
        tf = go.m_Transform.read()
        if tf.m_Father.path_id == 0:
            root_nodes[obj.path_id] = go

    for root_node in root_nodes.values():
        try:
            gifs = export_gameobject_animations(root_node)
            assert gifs
        except Exception as e:
            print(f"Error: {e}")
            continue
        for name, gif in gifs.items():
            fp = os.path.join(dst, name)
            if os.path.exists(fp):
                continue
            with open(fp, "wb") as f:
                f.write(gif)
