#!/usr/bin/env python3
"""
Cocos Creator prefab -> Unity prefab converter.
Supports both single-file and batch conversion with configurable paths.
"""
import json
import os
import re
import random
import argparse
import glob
import fnmatch

random.seed(42)


def gid():
    return random.randint(1000000000000000000, 9223372036854775806)


def yaml_string(value):
    """Quote arbitrary Cocos strings so names and multiline labels stay valid YAML."""
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def get_ref_idx(ref):
    if isinstance(ref, dict) and "__id__" in ref:
        return ref["__id__"]
    return None


# Unity built-in component GUIDs
GUID_IMAGE      = "fe87c0e1cc204ed48ad3b37840f39efc"
GUID_TEXT       = "5f7201a12d95ffc409449d95f23cf332"
GUID_BUTTON     = "4e29b1a8efbd4b44bb3f3716e73f07ff"
GUID_OUTLINE    = "e19747de3f5aca642ab2be37e372fb86"
GUID_INPUTFIELD = "d199490a83bb2b844b9695cbf13b01ef"
GUID_SLIDER     = "67db9e8f0e2ae9c40bc1e2b64352a6b4"
GUID_GRID       = "8a8695521f0d02e499659fee002a26c2"
GUID_VERTICAL   = "59f8146938fff824cb5fd77236b75775"
GUID_HORIZONTAL = "30649d3a9faa99c48a7b1166b86bf2a0"
GUID_SCROLLRECT = "1aa08ab6e0800fa44ae55d278d1423e3"
GUID_RECTMASK2D = "3312d7739989d2b4e91e6319e9a96d76"
GUID_FONT       = "1f61a3045ca384d658e06ced93fe9bc9"


def build_uuid_to_filename_map(cocos_sprite_dir, prefix_module=False):
    """Map Cocos UUIDs to sprite filenames by scanning .meta files."""
    uuid_map = {}
    for root, dirs, files in os.walk(cocos_sprite_dir):
        for f in files:
            if f.endswith('.meta'):
                meta_path = os.path.join(root, f)
                try:
                    with open(meta_path, 'r') as mf:
                        data = json.load(mf)
                    sub_metas = data.get('subMetas', {})
                    for sprite_name, meta_info in sub_metas.items():
                        if 'uuid' in meta_info:
                            uuid = meta_info['uuid']
                            orig_file = os.path.splitext(meta_path)[0]
                            filename = os.path.basename(orig_file)
                            if prefix_module:
                                relative = os.path.relpath(orig_file, cocos_sprite_dir)
                                relative_parts = relative.split(os.sep)
                                if "spine" not in (part.lower() for part in relative_parts[:-1]):
                                    filename = relative_parts[0] + "_" + filename
                            uuid_map[uuid] = filename
                except Exception:
                    pass
    return uuid_map


def build_uuid_to_border_map(cocos_sprite_dir):
    """Map Cocos sprite UUIDs to their nine-slice border (left, bottom, right, top).

    Border values live on each Cocos `subMetas` entry alongside its uuid. Any
    spriteFrame with a non-zero border is nine-slice and must be imported into
    Unity as Sliced with a matching spriteBorder.
    """
    border_map = {}
    for root, dirs, files in os.walk(cocos_sprite_dir):
        for f in files:
            if f.endswith('.meta'):
                meta_path = os.path.join(root, f)
                try:
                    with open(meta_path, 'r') as mf:
                        data = json.load(mf)
                    for sprite_name, meta_info in data.get('subMetas', {}).items():
                        if not isinstance(meta_info, dict) or 'uuid' not in meta_info:
                            continue
                        border = (
                            meta_info.get('borderLeft', 0) or 0,
                            meta_info.get('borderBottom', 0) or 0,
                            meta_info.get('borderRight', 0) or 0,
                            meta_info.get('borderTop', 0) or 0,
                        )
                        border_map[meta_info['uuid']] = border
                except Exception:
                    pass
    return border_map


def _format_border(left, bottom, right, top):
    return "{x: %g, y: %g, z: %g, w: %g}" % (left, bottom, right, top)


def _set_sprite_border_field(content, border):
    """Set the TextureImporter-level `spriteBorder` line (Single sprite mode)."""
    return re.sub(
        r'(spriteBorder:\s*)\{x: [^}]*\}',
        lambda m: m.group(1) + _format_border(*border),
        content,
        count=1,
    )


def _set_sprite_entry_border(content, sprite_name, border):
    """Set the `border` of the spriteSheet entry named `sprite_name`."""
    lines = content.splitlines(keepends=True)
    in_entry = False
    entry_name = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith('- serializedVersion:'):
            in_entry = True
            entry_name = None
            continue
        if in_entry and entry_name is None:
            m = re.match(r'\s*name:\s*(.*)', line)
            if m:
                entry_name = m.group(1).strip()
            continue
        if in_entry and entry_name == sprite_name:
            m = re.match(r'(\s*border:\s*)\{x: [^}]*\}', line)
            if m:
                lines[i] = m.group(1) + _format_border(*border) + '\n'
                return ''.join(lines)
    return content


def write_sprite_borders(cocos_sprite_dir, unity_textures_dir, prefix_module=False):
    """Copy Cocos nine-slice borders into Unity texture importer .meta files.

    Single-mode textures get their TextureImporter `spriteBorder` set; Multiple-mode
    textures get each matching spriteSheet entry's `border` set. Returns the number
    of Unity .meta files updated.
    """
    cocos_borders = {}
    for root, dirs, files in os.walk(cocos_sprite_dir):
        for f in files:
            if not f.endswith('.meta'):
                continue
            meta_path = os.path.join(root, f)
            try:
                with open(meta_path, 'r') as mf:
                    data = json.load(mf)
            except Exception:
                continue
            sub_metas = data.get('subMetas', {})
            if not sub_metas:
                continue
            orig_file = os.path.splitext(meta_path)[0]
            filename = os.path.basename(orig_file)
            if prefix_module:
                relative = os.path.relpath(orig_file, cocos_sprite_dir)
                relative_parts = relative.split(os.sep)
                if "spine" not in (part.lower() for part in relative_parts[:-1]):
                    filename = relative_parts[0] + "_" + filename
            borders = {}
            for sprite_name, meta_info in sub_metas.items():
                if not isinstance(meta_info, dict):
                    continue
                border = (
                    meta_info.get('borderLeft', 0) or 0,
                    meta_info.get('borderBottom', 0) or 0,
                    meta_info.get('borderRight', 0) or 0,
                    meta_info.get('borderTop', 0) or 0,
                )
                if any(v != 0 for v in border):
                    borders[sprite_name] = border
            if borders:
                cocos_borders[filename] = borders

    if not cocos_borders:
        return 0

    unity_meta_paths = {}
    for root, dirs, files in os.walk(unity_textures_dir):
        for f in files:
            if f.endswith('.meta'):
                unity_meta_paths[os.path.splitext(f)[0]] = os.path.join(root, f)

    updated = 0
    for filename, borders in cocos_borders.items():
        meta_path = unity_meta_paths.get(filename)
        if not meta_path:
            continue
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            continue

        mode_match = re.search(r'spriteMode:\s*(\d+)', content)
        mode = int(mode_match.group(1)) if mode_match else 1

        new_content = content
        if mode == 2:
            for sprite_name, border in borders.items():
                new_content = _set_sprite_entry_border(new_content, sprite_name, border)
        else:
            border = next(iter(borders.values()))
            new_content = _set_sprite_border_field(new_content, border)
            for sprite_name, b in borders.items():
                new_content = _set_sprite_entry_border(new_content, sprite_name, b)

        if new_content != content:
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            updated += 1

    return updated


def build_unity_guid_map(unity_textures_dir):
    """Map sprite filenames to Unity GUIDs by scanning .meta files."""
    guid_map = {}
    for root, dirs, files in os.walk(unity_textures_dir):
        for f in files:
            if f.endswith('.meta'):
                meta_path = os.path.join(root, f)
                try:
                    with open(meta_path, 'r') as mf:
                        content = mf.read()
                    match = re.search(r'guid: ([a-f0-9]{32})', content)
                    if match:
                        guid = match.group(1)
                        orig_file = os.path.splitext(meta_path)[0]
                        filename = os.path.basename(orig_file)
                        guid_map[filename] = guid
                except Exception:
                    pass
    return guid_map


def parse_prefab(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_prefab(data, out_path, cocos_uuid_map, unity_guid_map, script_guid=None,
                   cocos_border_map=None):
    root_idx = None
    for i, item in enumerate(data):
        if isinstance(item, dict) and item.get("__type__") == "cc.Node":
            parent = item.get("_parent")
            if parent is None or parent == {}:
                root_idx = i
                break
    if root_idx is None:
        for i, item in enumerate(data):
            if isinstance(item, dict) and item.get("__type__") == "cc.Node":
                root_idx = i
                break
    if root_idx is None:
        return False

    node_infos = {}

    def get_sprite_guid(comp_item):
        sf = comp_item.get("_spriteFrame", {})
        if isinstance(sf, dict) and "__uuid__" in sf:
            uuid = sf["__uuid__"]
            if uuid in cocos_uuid_map:
                filename = cocos_uuid_map[uuid]
                if filename in unity_guid_map:
                    return unity_guid_map[filename]
                # Migration projects prefix images with their bundle module
                # (for example common_btn_Cfm_M.png). Resolve that unique
                # renamed file while keeping the Cocos UUID lookup intact.
                candidates = [
                    guid for name, guid in unity_guid_map.items()
                    if name.endswith("_" + filename)
                ]
                if len(candidates) == 1:
                    return candidates[0]
        return None

    def get_sprite_border(comp_item):
        sf = comp_item.get("_spriteFrame", {})
        if isinstance(sf, dict) and "__uuid__" in sf:
            border = (cocos_border_map or {}).get(sf["__uuid__"])
            if border and any(v != 0 for v in border):
                return border
        return None

    def assign_ids(node_idx, parent_trans_id=None):
        node = data[node_idx]
        go_id = gid()
        trans_id = gid()

        pos_x, pos_y, pos_z = 0, 0, 0
        scale_x, scale_y, scale_z = 1, 1, 1
        trs = node.get("_trs", {})
        if isinstance(trs, dict):
            arr = trs.get("array", [])
            if isinstance(arr, list):
                if len(arr) >= 3:
                    pos_x, pos_y, pos_z = arr[0], arr[1], arr[2]
                if len(arr) >= 10:
                    scale_x, scale_y, scale_z = arr[7], arr[8], arr[9]

        sz = node.get("_contentSize", {})
        if isinstance(sz, dict):
            w, h = sz.get("width", 100), sz.get("height", 100)
        else:
            w, h = 100, 100

        ap = node.get("_anchorPoint", {})
        if isinstance(ap, dict):
            ax, ay = ap.get("x", 0.5), ap.get("y", 0.5)
        else:
            ax, ay = 0.5, 0.5

        active = 1 if node.get("_active", True) else 0
        name = node.get("_name", "Node")

        opacity = node.get("_opacity", 255) / 255.0
        color_data = node.get("_color", {})
        if isinstance(color_data, dict):
            r = color_data.get("r", 255) / 255.0
            g = color_data.get("g", 255) / 255.0
            b = color_data.get("b", 255) / 255.0
            a = color_data.get("a", 255) / 255.0
        else:
            r = g = b = a = 1.0

        components = []
        needs_canvas_renderer = False

        def referenced_component_node(ref):
            component_idx = get_ref_idx(ref)
            if component_idx is None or not 0 <= component_idx < len(data):
                return None
            component = data[component_idx]
            if not isinstance(component, dict):
                return None
            return get_ref_idx(component.get("node"))

        def referenced_node(ref):
            node_idx = get_ref_idx(ref)
            if node_idx is None or not 0 <= node_idx < len(data):
                return None
            node = data[node_idx]
            return node_idx if isinstance(node, dict) and node.get("__type__") == "cc.Node" else None

        for cref in node.get("_components", []):
            cidx = get_ref_idx(cref)
            if cidx is None or cidx >= len(data):
                continue
            citem = data[cidx]
            ctype = citem.get("__type__", "")

            if ctype == "cc.Sprite":
                needs_canvas_renderer = True
                sprite_guid = get_sprite_guid(citem)
                sprite_frame = citem.get("_spriteFrame")
                sprite_border = get_sprite_border(citem)
                components.append({
                    "type": "Image",
                    "id": gid(),
                    "guid": sprite_guid,
                    "has_sprite_frame": isinstance(sprite_frame, dict) and "__uuid__" in sprite_frame,
                    "sliced": sprite_border is not None,
                })
            elif ctype == "cc.Label" or ctype == "cc.RichText":
                needs_canvas_renderer = True
                text = citem.get("_string", "")
                font_size = citem.get("_fontSize", 28)
                line_height = citem.get("_lineHeight", font_size)
                h_align = citem.get("_N$horizontalAlign", 1)
                h_map = {0: 0, 1: 4, 2: 2}
                components.append({
                    "type": "Text",
                    "id": gid(),
                    "text": text,
                    "fontSize": font_size,
                    "lineHeight": line_height,
                    "alignment": h_map.get(h_align, 4),
                    "bestFit": True
                })
            elif ctype == "cc.LabelOutline":
                outline_color = citem.get("_color", {})
                outline_width = citem.get("_width", 1)
                components.append({
                    "type": "Outline",
                    "id": gid(),
                    "color": outline_color,
                    "width": outline_width
                })
            elif ctype == "cc.Button":
                components.append({
                    "type": "Button",
                    "id": gid()
                })
            elif ctype == "cc.Layout":
                layout_type = citem.get("_N$layoutType", 0)
                components.append({
                    "type": "Layout",
                    "id": gid(),
                    "layoutType": layout_type,
                    "paddingLeft": citem.get("_N$paddingLeft", 0),
                    "paddingRight": citem.get("_N$paddingRight", 0),
                    "paddingTop": citem.get("_N$paddingTop", 0),
                    "paddingBottom": citem.get("_N$paddingBottom", 0),
                    "spacingX": citem.get("_N$spacingX", 0),
                    "spacingY": citem.get("_N$spacingY", 0),
                })
            elif ctype == "cc.ScrollView":
                content_node = referenced_node(citem.get("content") or citem.get("_N$content"))
                viewport_node = None
                if content_node is not None:
                    viewport_node = get_ref_idx(data[content_node].get("_parent"))
                components.append({
                    "type": "ScrollRect",
                    "id": gid(),
                    "content_node": content_node,
                    "viewport_node": viewport_node,
                    "horizontal": bool(citem.get("horizontal", False)),
                    "vertical": bool(citem.get("vertical", True)),
                })
            elif ctype == "cc.ProgressBar" or ctype == "cc.Slider":
                is_progress_bar = ctype == "cc.ProgressBar"
                mode = citem.get("_N$mode", citem.get("_N$direction", 0))
                reverse = bool(citem.get("_N$reverse", False))
                direction = (2 if mode == 1 else 0) + (1 if reverse else 0)
                components.append({
                    "type": "Slider",
                    "id": gid(),
                    "fill_node": referenced_component_node(citem.get("_N$barSprite")),
                    "handle_node": referenced_component_node(citem.get("_N$handle")),
                    "direction": direction,
                    "value": citem.get("_N$progress", 0),
                    "interactable": not is_progress_bar,
                })
            elif ctype == "cc.Mask":
                components.append({
                    "type": "RectMask2D",
                    "id": gid()
                })
            elif ctype == "cc.EditBox":
                components.append({
                    "type": "InputField",
                    "id": gid(),
                    "background_node": referenced_component_node(citem.get("_N$background")),
                    "text_node": referenced_component_node(citem.get("_N$textLabel")),
                    "placeholder_node": referenced_component_node(citem.get("_N$placeholderLabel")),
                    "character_limit": citem.get("maxLength", 0),
                })
            elif ctype == "cc.BlockInputEvents":
                components.append({
                    "type": "CanvasGroup",
                    "id": gid()
                })

        if parent_trans_id is None and script_guid:
            components.append({
                "type": "Script",
                "id": gid(),
                "guid": script_guid,
            })

        children = []
        for c in node.get("_children", []):
            cidx = get_ref_idx(c)
            if cidx is not None and 0 <= cidx < len(data):
                if isinstance(data[cidx], dict) and data[cidx].get("__type__") == "cc.Node":
                    children.append(cidx)

        node_infos[node_idx] = {
            "go_id": go_id,
            "trans_id": trans_id,
            "parent_trans_id": parent_trans_id,
            "name": name,
            "active": active,
            "pos": (pos_x, pos_y, pos_z),
            "scale": (scale_x, scale_y, scale_z),
            "size": (w, h),
            "anchor": (ax, ay),
            "color": (r, g, b, a * opacity),
            "components": components,
            "needs_canvas_renderer": needs_canvas_renderer,
            "children": children,
        }

        for cidx in children:
            assign_ids(cidx, trans_id)

    assign_ids(root_idx)

    slider_fill_nodes = {
        component["fill_node"]
        for info in node_infos.values()
        for component in info["components"]
        if component["type"] == "Slider" and component.get("fill_node") in node_infos
    }

    def get_child_content_size(node_idx):
        children = node_infos[node_idx]["children"]
        if children:
            first_child = children[0]
            if first_child < len(data):
                child_node = data[first_child]
                sz = child_node.get("_contentSize", {})
                if isinstance(sz, dict):
                    return (sz.get("width", 100), sz.get("height", 100))
        return (180, 243)

    def component_id(node_idx, component_type):
        if node_idx not in node_infos:
            return 0
        return next(
            (component["id"] for component in node_infos[node_idx]["components"]
             if component["type"] == component_type),
            0,
        )

    lines = []
    lines.append("%YAML 1.1")
    lines.append("%TAG !u! tag:unity3d.com,2011:")
    lines.append("")

    def write_node(node_idx):
        info = node_infos[node_idx]
        go_id = info["go_id"]
        trans_id = info["trans_id"]
        name = info["name"]
        active = info["active"]
        px, py, pz = info["pos"]
        sx, sy, sz = info["scale"]
        w, h = info["size"]
        ax, ay = info["anchor"]
        r, g, b, a = info["color"]
        parent_trans = info.get("parent_trans_id")
        needs_canvas = info["needs_canvas_renderer"]

        # A prefab root is positioned by its parent Canvas at runtime. Keeping
        # the Cocos canvas-space offset here would shift the entire Unity view.
        if parent_trans is None:
            px = py = pz = 0

        comp_ids = [str(trans_id)]

        canvas_id = None
        if needs_canvas:
            canvas_id = gid()
            comp_ids.append(str(canvas_id))

        for c in info["components"]:
            comp_ids.append(str(c["id"]))

        lines.append("--- !u!1 &" + str(go_id))
        lines.append("GameObject:")
        lines.append("  m_ObjectHideFlags: 0")
        lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
        lines.append("  m_PrefabInstance: {fileID: 0}")
        lines.append("  m_PrefabAsset: {fileID: 0}")
        lines.append("  serializedVersion: 6")
        lines.append("  m_Component:")
        for cid in comp_ids:
            lines.append("  - component: {fileID: " + cid + "}")
        lines.append("  m_Layer: 5")
        lines.append("  m_Name: " + yaml_string(name))
        lines.append("  m_TagString: Untagged")
        lines.append("  m_Icon: {fileID: 0}")
        lines.append("  m_NavMeshLayer: 0")
        lines.append("  m_StaticEditorFlags: 0")
        lines.append("  m_IsActive: " + str(active))
        lines.append("")

        lines.append("--- !u!224 &" + str(trans_id))
        lines.append("RectTransform:")
        lines.append("  m_ObjectHideFlags: 0")
        lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
        lines.append("  m_PrefabInstance: {fileID: 0}")
        lines.append("  m_PrefabAsset: {fileID: 0}")
        lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
        lines.append("  m_LocalRotation: {x: 0, y: 0, z: 0, w: 1}")
        lines.append("  m_LocalPosition: {x: " + str(px) + ", y: " + str(py) + ", z: " + str(pz) + "}")
        lines.append("  m_LocalScale: {x: " + str(sx) + ", y: " + str(sy) + ", z: " + str(sz) + "}")
        lines.append("  m_ConstrainProportionsScale: 0")
        if info["children"]:
            lines.append("  m_Children:")
            for cidx in info["children"]:
                cinfo = node_infos[cidx]
                lines.append("  - {fileID: " + str(cinfo["trans_id"]) + "}")
        else:
            lines.append("  m_Children: []")
        if parent_trans is not None:
            lines.append("  m_Father: {fileID: " + str(parent_trans) + "}")
        else:
            lines.append("  m_Father: {fileID: 0}")
        lines.append("  m_RootOrder: 0")
        lines.append("  m_LocalEulerAnglesHint: {x: 0, y: 0, z: 0}")
        if node_idx in slider_fill_nodes:
            lines.append("  m_AnchorMin: {x: 0, y: 0}")
            lines.append("  m_AnchorMax: {x: 1, y: 1}")
            lines.append("  m_AnchoredPosition: {x: 0, y: 0}")
            lines.append("  m_SizeDelta: {x: -6, y: -6}")
        else:
            lines.append("  m_AnchorMin: {x: 0.5, y: 0.5}")
            lines.append("  m_AnchorMax: {x: 0.5, y: 0.5}")
            lines.append("  m_AnchoredPosition: {x: " + str(px) + ", y: " + str(py) + "}")
            lines.append("  m_SizeDelta: {x: " + str(w) + ", y: " + str(h) + "}")
        lines.append("  m_Pivot: {x: " + str(ax) + ", y: " + str(ay) + "}")
        lines.append("")

        if needs_canvas and canvas_id:
            lines.append("--- !u!222 &" + str(canvas_id))
            lines.append("CanvasRenderer:")
            lines.append("  m_ObjectHideFlags: 0")
            lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
            lines.append("  m_PrefabInstance: {fileID: 0}")
            lines.append("  m_PrefabAsset: {fileID: 0}")
            lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
            lines.append("  m_CullTransparentMesh: 1")
            lines.append("")

        for c in info["components"]:
            cid = c["id"]
            ct = c["type"]

            if ct == "Image":
                image_alpha = a if c.get("has_sprite_frame", False) else 0
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_IMAGE + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Material: {fileID: 0}")
                lines.append("  m_Color: {r: " + str(r) + ", g: " + str(g) + ", b: " + str(b) + ", a: " + str(image_alpha) + "}")
                lines.append("  m_RaycastTarget: 1")
                lines.append("  m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}")
                lines.append("  m_Maskable: 1")
                lines.append("  m_OnCullStateChanged:")
                lines.append("    m_PersistentCalls:")
                lines.append("      m_Calls: []")
                if c.get("guid"):
                    lines.append("  m_Sprite: {fileID: 21300000, guid: " + c["guid"] + ", type: 3}")
                else:
                    lines.append("  m_Sprite: {fileID: 0}")
                if node_idx in slider_fill_nodes:
                    image_type = "3"
                elif c.get("sliced"):
                    image_type = "1"
                else:
                    image_type = "0"
                lines.append("  m_Type: " + image_type)
                lines.append("  m_PreserveAspect: 0")
                lines.append("  m_FillCenter: 1")
                lines.append("  m_FillMethod: " + ("0" if node_idx in slider_fill_nodes else "4"))
                lines.append("  m_FillAmount: 1")
                lines.append("  m_FillClockwise: 1")
                lines.append("  m_FillOrigin: 0")
                lines.append("  m_UseSpriteMesh: 0")
                lines.append("  m_PixelsPerUnitMultiplier: 1")
                lines.append("")

            elif ct == "Text":
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_TEXT + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Material: {fileID: 0}")
                lines.append("  m_Color: {r: " + str(r) + ", g: " + str(g) + ", b: " + str(b) + ", a: " + str(a) + "}")
                lines.append("  m_RaycastTarget: 1")
                lines.append("  m_RaycastPadding: {x: 0, y: 0, z: 0, w: 0}")
                lines.append("  m_Maskable: 1")
                lines.append("  m_OnCullStateChanged:")
                lines.append("    m_PersistentCalls:")
                lines.append("      m_Calls: []")
                lines.append("  m_FontData:")
                lines.append("    m_Font: {fileID: 12800000, guid: " + GUID_FONT + ", type: 3}")
                lines.append("    m_FontSize: " + str(c["fontSize"]))
                lines.append("    m_FontStyle: 0")
                lines.append("    m_BestFit: 1")
                lines.append("    m_MinSize: 1")
                lines.append("    m_MaxSize: " + str(c["fontSize"]))
                lines.append("    m_Alignment: " + str(c["alignment"]))
                lines.append("    m_AlignByGeometry: 0")
                lines.append("    m_RichText: 0")
                lines.append("    m_HorizontalOverflow: 0")
                lines.append("    m_VerticalOverflow: 0")
                lines.append("    m_LineSpacing: 1")
                lines.append("  m_Text: " + yaml_string(c["text"]))
                lines.append("")

            elif ct == "Outline":
                outline_color = c.get("color", {})
                if isinstance(outline_color, dict):
                    oc_r = outline_color.get("r", 0) / 255.0
                    oc_g = outline_color.get("g", 0) / 255.0
                    oc_b = outline_color.get("b", 0) / 255.0
                    oc_a = outline_color.get("a", 255) / 255.0
                else:
                    oc_r = oc_g = oc_b = 0.0
                    oc_a = 1.0

                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_OUTLINE + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_EffectColor: {r: " + str(oc_r) + ", g: " + str(oc_g) + ", b: " + str(oc_b) + ", a: " + str(oc_a) + "}")
                lines.append("  m_EffectDistance: {x: " + str(c.get("width", 1)) + ", y: " + str(c.get("width", 1)) + "}")
                lines.append("  m_UseGraphicAlpha: 1")
                lines.append("")

            elif ct == "Button":
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_BUTTON + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Navigation:")
                lines.append("    m_Mode: 3")
                lines.append("    m_WrapAround: 0")
                lines.append("    m_SelectOnUp: {fileID: 0}")
                lines.append("    m_SelectOnDown: {fileID: 0}")
                lines.append("    m_SelectOnLeft: {fileID: 0}")
                lines.append("    m_SelectOnRight: {fileID: 0}")
                lines.append("  m_Transition: 1")
                lines.append("  m_Colors:")
                lines.append("    m_NormalColor: {r: 1, g: 1, b: 1, a: 1}")
                lines.append("    m_HighlightedColor: {r: 0.96, g: 0.96, b: 0.96, a: 1}")
                lines.append("    m_PressedColor: {r: 0.78, g: 0.78, b: 0.78, a: 1}")
                lines.append("    m_SelectedColor: {r: 0.96, g: 0.96, b: 0.96, a: 1}")
                lines.append("    m_DisabledColor: {r: 0.78, g: 0.78, b: 0.78, a: 0.5}")
                lines.append("    m_ColorMultiplier: 1")
                lines.append("    m_FadeDuration: 0.1")
                lines.append("  m_SpriteState:")
                lines.append("    m_HighlightedSprite: {fileID: 0}")
                lines.append("    m_PressedSprite: {fileID: 0}")
                lines.append("    m_SelectedSprite: {fileID: 0}")
                lines.append("    m_DisabledSprite: {fileID: 0}")
                lines.append("  m_AnimationTriggers:")
                lines.append("    m_NormalTrigger: Normal")
                lines.append("    m_HighlightedTrigger: Highlighted")
                lines.append("    m_PressedTrigger: Pressed")
                lines.append("    m_SelectedTrigger: Selected")
                lines.append("    m_DisabledTrigger: Disabled")
                lines.append("  m_Interactable: 1")
                lines.append("  m_TargetGraphic: {fileID: 0}")
                lines.append("  m_OnClick:")
                lines.append("    m_PersistentCalls:")
                lines.append("      m_Calls: []")
                lines.append("")

            elif ct == "Slider":
                fill_node = c.get("fill_node")
                handle_node = c.get("handle_node")
                fill_id = node_infos[fill_node]["trans_id"] if fill_node in node_infos else 0
                handle_id = node_infos[handle_node]["trans_id"] if handle_node in node_infos else 0
                target_graphic_id = next(
                    (component["id"] for component in info["components"] if component["type"] == "Image"),
                    0,
                )
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_SLIDER + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Navigation:")
                lines.append("    m_Mode: 3")
                lines.append("    m_WrapAround: 0")
                lines.append("    m_SelectOnUp: {fileID: 0}")
                lines.append("    m_SelectOnDown: {fileID: 0}")
                lines.append("    m_SelectOnLeft: {fileID: 0}")
                lines.append("    m_SelectOnRight: {fileID: 0}")
                lines.append("  m_Transition: 1")
                lines.append("  m_Colors:")
                lines.append("    m_NormalColor: {r: 1, g: 1, b: 1, a: 1}")
                lines.append("    m_HighlightedColor: {r: 0.96, g: 0.96, b: 0.96, a: 1}")
                lines.append("    m_PressedColor: {r: 0.78, g: 0.78, b: 0.78, a: 1}")
                lines.append("    m_SelectedColor: {r: 0.96, g: 0.96, b: 0.96, a: 1}")
                lines.append("    m_DisabledColor: {r: 0.78, g: 0.78, b: 0.78, a: 0.5}")
                lines.append("    m_ColorMultiplier: 1")
                lines.append("    m_FadeDuration: 0.1")
                lines.append("  m_SpriteState:")
                lines.append("    m_HighlightedSprite: {fileID: 0}")
                lines.append("    m_PressedSprite: {fileID: 0}")
                lines.append("    m_SelectedSprite: {fileID: 0}")
                lines.append("    m_DisabledSprite: {fileID: 0}")
                lines.append("  m_AnimationTriggers:")
                lines.append("    m_NormalTrigger: Normal")
                lines.append("    m_HighlightedTrigger: Highlighted")
                lines.append("    m_PressedTrigger: Pressed")
                lines.append("    m_SelectedTrigger: Selected")
                lines.append("    m_DisabledTrigger: Disabled")
                lines.append("  m_Interactable: " + ("1" if c.get("interactable", True) else "0"))
                lines.append("  m_TargetGraphic: {fileID: " + str(target_graphic_id) + "}")
                lines.append("  m_FillRect: {fileID: " + str(fill_id) + "}")
                lines.append("  m_HandleRect: {fileID: " + str(handle_id) + "}")
                lines.append("  m_Direction: " + str(c.get("direction", 0)))
                lines.append("  m_MinValue: 0")
                lines.append("  m_MaxValue: 1")
                lines.append("  m_WholeNumbers: 0")
                lines.append("  m_Value: " + str(c.get("value", 0)))
                lines.append("  m_OnValueChanged:")
                lines.append("    m_PersistentCalls:")
                lines.append("      m_Calls: []")
                lines.append("")

            elif ct == "ScrollRect":
                content_id = node_infos[c["content_node"]]["trans_id"] if c.get("content_node") in node_infos else 0
                viewport_id = node_infos[c["viewport_node"]]["trans_id"] if c.get("viewport_node") in node_infos else 0
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_SCROLLRECT + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Content: {fileID: " + str(content_id) + "}")
                lines.append("  m_Horizontal: " + ("1" if c.get("horizontal") else "0"))
                lines.append("  m_Vertical: " + ("1" if c.get("vertical") else "0"))
                lines.append("  m_MovementType: 1")
                lines.append("  m_Elasticity: 0.1")
                lines.append("  m_Inertia: 1")
                lines.append("  m_DecelerationRate: 0.135")
                lines.append("  m_ScrollSensitivity: 1")
                lines.append("  m_Viewport: {fileID: " + str(viewport_id) + "}")
                lines.append("  m_HorizontalScrollbar: {fileID: 0}")
                lines.append("  m_VerticalScrollbar: {fileID: 0}")
                lines.append("  m_HorizontalScrollbarVisibility: 0")
                lines.append("  m_VerticalScrollbarVisibility: 0")
                lines.append("  m_HorizontalScrollbarSpacing: 0")
                lines.append("  m_VerticalScrollbarSpacing: 0")
                lines.append("  m_OnValueChanged:")
                lines.append("    m_PersistentCalls:")
                lines.append("      m_Calls: []")
                lines.append("")

            elif ct == "Layout":
                layout_type = c.get("layoutType", 0)
                if layout_type == 3:
                    cell_w, cell_h = get_child_content_size(node_idx)
                    layout_guid = GUID_GRID
                    lines.append("--- !u!114 &" + str(cid))
                    lines.append("MonoBehaviour:")
                    lines.append("  m_ObjectHideFlags: 0")
                    lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                    lines.append("  m_PrefabInstance: {fileID: 0}")
                    lines.append("  m_PrefabAsset: {fileID: 0}")
                    lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                    lines.append("  m_Enabled: 1")
                    lines.append("  m_EditorHideFlags: 0")
                    lines.append("  m_Script: {fileID: 11500000, guid: " + layout_guid + ", type: 3}")
                    lines.append("  m_Name: ")
                    lines.append("  m_EditorClassIdentifier: ")
                    lines.append("  m_Padding:")
                    lines.append("    m_Left: " + str(c.get("paddingLeft", 0)))
                    lines.append("    m_Right: " + str(c.get("paddingRight", 0)))
                    lines.append("    m_Top: " + str(c.get("paddingTop", 0)))
                    lines.append("    m_Bottom: " + str(c.get("paddingBottom", 0)))
                    lines.append("  m_ChildAlignment: 0")
                    lines.append("  m_StartCorner: 0")
                    lines.append("  m_StartAxis: 0")
                    lines.append("  m_CellSize: {x: " + str(cell_w) + ", y: " + str(cell_h) + "}")
                    lines.append("  m_Spacing: {x: " + str(c.get("spacingX", 0)) + ", y: " + str(c.get("spacingY", 0)) + "}")
                    lines.append("  m_Constraint: 0")
                    lines.append("  m_ConstraintCount: 2")
                    lines.append("")

                elif layout_type == 2:
                    layout_guid = GUID_VERTICAL
                    lines.append("--- !u!114 &" + str(cid))
                    lines.append("MonoBehaviour:")
                    lines.append("  m_ObjectHideFlags: 0")
                    lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                    lines.append("  m_PrefabInstance: {fileID: 0}")
                    lines.append("  m_PrefabAsset: {fileID: 0}")
                    lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                    lines.append("  m_Enabled: 1")
                    lines.append("  m_EditorHideFlags: 0")
                    lines.append("  m_Script: {fileID: 11500000, guid: " + layout_guid + ", type: 3}")
                    lines.append("  m_Name: ")
                    lines.append("  m_EditorClassIdentifier: ")
                    lines.append("  m_Padding:")
                    lines.append("    m_Left: " + str(c.get("paddingLeft", 0)))
                    lines.append("    m_Right: " + str(c.get("paddingRight", 0)))
                    lines.append("    m_Top: " + str(c.get("paddingTop", 0)))
                    lines.append("    m_Bottom: " + str(c.get("paddingBottom", 0)))
                    lines.append("  m_ChildAlignment: 0")
                    lines.append("  m_Spacing: " + str(c.get("spacingY", 0)))
                    lines.append("  m_ChildForceExpandWidth: 0")
                    lines.append("  m_ChildForceExpandHeight: 0")
                    lines.append("  m_ChildControlWidth: 0")
                    lines.append("  m_ChildControlHeight: 0")
                    lines.append("  m_ChildScaleWidth: 0")
                    lines.append("  m_ChildScaleHeight: 0")
                    lines.append("")

                else:
                    layout_guid = GUID_HORIZONTAL
                    lines.append("--- !u!114 &" + str(cid))
                    lines.append("MonoBehaviour:")
                    lines.append("  m_ObjectHideFlags: 0")
                    lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                    lines.append("  m_PrefabInstance: {fileID: 0}")
                    lines.append("  m_PrefabAsset: {fileID: 0}")
                    lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                    lines.append("  m_Enabled: 1")
                    lines.append("  m_EditorHideFlags: 0")
                    lines.append("  m_Script: {fileID: 11500000, guid: " + layout_guid + ", type: 3}")
                    lines.append("  m_Name: ")
                    lines.append("  m_EditorClassIdentifier: ")
                    lines.append("  m_Padding:")
                    lines.append("    m_Left: " + str(c.get("paddingLeft", 0)))
                    lines.append("    m_Right: " + str(c.get("paddingRight", 0)))
                    lines.append("    m_Top: " + str(c.get("paddingTop", 0)))
                    lines.append("    m_Bottom: " + str(c.get("paddingBottom", 0)))
                    lines.append("  m_ChildAlignment: 0")
                    lines.append("  m_Spacing: " + str(c.get("spacingX", 0)))
                    lines.append("  m_ChildForceExpandWidth: 0")
                    lines.append("  m_ChildForceExpandHeight: 0")
                    lines.append("  m_ChildControlWidth: 0")
                    lines.append("  m_ChildControlHeight: 0")
                    lines.append("  m_ChildScaleWidth: 0")
                    lines.append("  m_ChildScaleHeight: 0")
                    lines.append("")

            elif ct == "Script":
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + c["guid"] + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("")

            elif ct == "RectMask2D":
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_RECTMASK2D + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Padding: {x: 0, y: 0, z: 0, w: 0}")
                lines.append("  m_Softness: {x: 0, y: 0}")
                lines.append("")

            elif ct == "InputField":
                target_graphic_id = component_id(c.get("background_node"), "Image")
                text_component_id = component_id(c.get("text_node"), "Text")
                placeholder_id = component_id(c.get("placeholder_node"), "Text")
                lines.append("--- !u!114 &" + str(cid))
                lines.append("MonoBehaviour:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_EditorHideFlags: 0")
                lines.append("  m_Script: {fileID: 11500000, guid: " + GUID_INPUTFIELD + ", type: 3}")
                lines.append("  m_Name: ")
                lines.append("  m_EditorClassIdentifier: ")
                lines.append("  m_Interactable: 1")
                lines.append("  m_TargetGraphic: {fileID: " + str(target_graphic_id) + "}")
                lines.append("  m_TextComponent: {fileID: " + str(text_component_id) + "}")
                lines.append("  m_Placeholder: {fileID: " + str(placeholder_id) + "}")
                lines.append("  m_ContentType: 0")
                lines.append("  m_InputType: 0")
                lines.append("  m_CharacterValidation: 0")
                lines.append("  m_LineType: 0")
                lines.append("  m_CaretBlinkRate: 0.85")
                lines.append("  m_CaretWidth: 1")
                lines.append("  m_ReadOnly: 0")
                lines.append("  m_CharacterLimit: " + str(c.get("character_limit", 0)))
                lines.append("")

            elif ct == "CanvasGroup":
                lines.append("--- !u!225 &" + str(cid))
                lines.append("CanvasGroup:")
                lines.append("  m_ObjectHideFlags: 0")
                lines.append("  m_CorrespondingSourceObject: {fileID: 0}")
                lines.append("  m_PrefabInstance: {fileID: 0}")
                lines.append("  m_PrefabAsset: {fileID: 0}")
                lines.append("  m_GameObject: {fileID: " + str(go_id) + "}")
                lines.append("  m_Enabled: 1")
                lines.append("  m_Alpha: 1")
                lines.append("  m_Interactable: 1")
                lines.append("  m_BlocksRaycasts: 1")
                lines.append("  m_IgnoreParentGroups: 0")
                lines.append("")

        for cidx in info["children"]:
            write_node(cidx)

    write_node(root_idx)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return True


def find_script_guid(unity_scripts_dir, prefab_name):
    if not unity_scripts_dir:
        return None
    for root, dirs, files in os.walk(unity_scripts_dir):
        for filename in files:
            if not filename.endswith(".cs.meta"):
                continue
            script_path = os.path.join(root, filename[:-5])
            try:
                text = open(script_path, encoding="utf-8").read()
                if re.search(r"\bclass\s+" + re.escape(prefab_name) + r"\b", text):
                    meta = open(os.path.join(root, filename), encoding="utf-8").read()
                    match = re.search(r"^guid:\s*([0-9a-f]{32})", meta, re.MULTILINE)
                    return match.group(1) if match else None
            except OSError:
                pass
    return None


def convert_single(src_path, out_path, cocos_sprite_dir, unity_textures_dir,
                   prefix_module=False, unity_scripts_dir=None, skip_borders=False):
    """Convert a single Cocos prefab to Unity prefab."""
    cocos_uuid_map = build_uuid_to_filename_map(cocos_sprite_dir, prefix_module)
    cocos_border_map = build_uuid_to_border_map(cocos_sprite_dir)
    unity_guid_map = build_unity_guid_map(unity_textures_dir)
    if not skip_borders:
        write_sprite_borders(cocos_sprite_dir, unity_textures_dir, prefix_module)
    data = parse_prefab(src_path)
    prefab_name = os.path.splitext(os.path.basename(src_path))[0]
    script_guid = find_script_guid(unity_scripts_dir, prefab_name)
    return convert_prefab(data, out_path, cocos_uuid_map, unity_guid_map,
                          script_guid, cocos_border_map)


def convert_batch(cocos_prefab_dir, output_dir, cocos_sprite_dir, unity_textures_dir,
                  pattern="*.prefab", prefix_module=False, unity_scripts_dir=None,
                  skip_borders=False):
    """Batch convert all Cocos prefabs in a directory."""
    os.makedirs(output_dir, exist_ok=True)

    cocos_uuid_map = build_uuid_to_filename_map(cocos_sprite_dir, prefix_module)
    cocos_border_map = build_uuid_to_border_map(cocos_sprite_dir)
    unity_guid_map = build_unity_guid_map(unity_textures_dir)
    if not skip_borders:
        write_sprite_borders(cocos_sprite_dir, unity_textures_dir, prefix_module)

    prefab_files = []
    for root, dirs, files in os.walk(cocos_prefab_dir):
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                prefab_files.append(os.path.join(root, f))

    success = 0
    for prefab_path in sorted(prefab_files):
        try:
            data = parse_prefab(prefab_path)
            prefab_name = os.path.splitext(os.path.basename(prefab_path))[0]
            out_path = os.path.join(output_dir, f"{prefab_name}.prefab")
            script_guid = find_script_guid(unity_scripts_dir, prefab_name)
            if convert_prefab(data, out_path, cocos_uuid_map, unity_guid_map,
                              script_guid, cocos_border_map):
                success += 1
                print(f"  [OK] {prefab_name}")
            else:
                print(f"  [FAIL] {prefab_name}: No root node")
        except Exception as e:
            print(f"  [ERR] {os.path.basename(prefab_path)}: {e}")

    print(f"\nConverted: {success}/{len(prefab_files)}")
    return success


def main():
    parser = argparse.ArgumentParser(description="Convert Cocos Creator prefabs to Unity prefabs")
    parser.add_argument("--input", "-i", required=True, help="Input Cocos .prefab file or directory")
    parser.add_argument("--output", "-o", required=True, help="Output Unity .prefab file or directory")
    parser.add_argument("--cocos-sprites", default="cocos_game_arrow/assets/subb/sprite",
                        help="Path to Cocos sprite directory (for UUID resolution)")
    parser.add_argument("--unity-textures", default="unity_game_arrow/Assets/GameRes/Textures",
                        help="Path to Unity textures directory (for GUID resolution)")
    parser.add_argument("--batch", "-b", action="store_true",
                        help="Batch mode: input/output are directories")
    parser.add_argument("--prefix-module", action="store_true",
                        help="Resolve images renamed with their top-level module prefix")
    parser.add_argument("--unity-scripts",
                        help="Unity scripts directory used to attach a view class matching the prefab name")
    parser.add_argument("--skip-borders", action="store_true",
                        help="Do not write nine-slice sprite borders into Unity .meta files")

    args = parser.parse_args()

    if args.batch:
        convert_batch(args.input, args.output, args.cocos_sprites, args.unity_textures,
                      prefix_module=args.prefix_module, unity_scripts_dir=args.unity_scripts,
                      skip_borders=args.skip_borders)
    else:
        convert_single(args.input, args.output, args.cocos_sprites, args.unity_textures,
                       args.prefix_module, args.unity_scripts, args.skip_borders)
        print(f"Converted: {args.output}")


if __name__ == "__main__":
    main()
