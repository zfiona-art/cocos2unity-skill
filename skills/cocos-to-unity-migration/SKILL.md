---
name: cocos-to-unity-prefab-migration
description: >
  Migrate Cocos Creator prefab files (JSON format) to Unity prefab files (YAML format).
  Use when:
  - Converting Cocos Creator .prefab JSON files to Unity .prefab YAML files
  - Mapping Cocos components (cc.Sprite, cc.Label, cc.Button, cc.Layout, cc.ScrollView, etc.) to Unity equivalents (Image, Text, Button, GridLayoutGroup, VerticalLayoutGroup, ScrollRect, etc.)
  - Resolving sprite references from Cocos UUID-based system to Unity GUID-based system via .meta file cross-referencing
  - Preserving node hierarchy, sibling order, and transform data during migration
  - Batch converting multiple Cocos prefabs to Unity prefabs
  - Porting Cocos TS/JS game logic scripts to Unity C#
  - Migrating Cocos event system (EventMgr) to Unity MessageManager
  - Porting Cocos Model layer to C#
  - Copying and organizing Cocos resources (sprites, audio, JSON configs) into Unity
---

# Cocos to Unity Prefab Migration

## Overview

Convert Cocos Creator prefabs (JSON) into Unity prefabs (YAML) while preserving node hierarchy, transform data, and component behavior. Also covers script migration, event system porting, model layer conversion, and resource migration.

## Component Mapping

| Cocos Component | Unity Component | GUID |
|---|---|---|
| `cc.Sprite` | `Image` | `fe87c0e1cc204ed48ad3b37840f39efc` |
| `cc.Label` | `Text` | `5f7201a12d95ffc409449d95f23cf332` |
| `cc.LabelOutline` | `Outline` | `e19747de3f5aca642ab2be37e372fb86` |
| `cc.Button` | `Button` | `4e29b1a8efbd4b44bb3f3716e73f07ff` |
| `cc.Layout` (type=3/GRID) | `GridLayoutGroup` | `8a8695521f0d02e499659fee002a26c2` |
| `cc.Layout` (type=2/VERTICAL) | `VerticalLayoutGroup` | `59f8146938fff824cb5fd77236b75775` |
| `cc.Layout` (type=0/HORIZONTAL) | `HorizontalLayoutGroup` | `30649d3a9faa99c48a7b1166b86bf2a0` |
| `cc.ScrollView` | `ScrollRect` | `1aa08ab6e0800fa44ae55d278d1423e3` |
| `cc.ProgressBar` / `cc.Slider` | `Slider` | `67db9e8f0e2ae9c40bc1e2b64352a6b4` |
| `cc.EditBox` | `InputField` | `d199490a83bb2b844b9695cbf13b01ef` |
| `cc.Mask` | `RectMask2D` | `3312d7739989d2b4e91e6319e9a96d76` |

### Font Reference

All Text components use Baloo2-Bold: `guid: 1f61a3045ca384d658e06ced93fe9bc9`

## Sprite Reference Resolution

Sprites are resolved in two steps:

1. **Cocos UUID -> Filename**: Scan `.meta` files under the Cocos sprite directory. Extract `subMetas -> <name> -> uuid` mappings.
2. **Filename -> Unity GUID**: Scan `.meta` files under the Unity textures directory. Extract `guid: <32-char-hex>`.

When copying image assets, also read each Cocos `subMetas` entry's `borderLeft`, `borderBottom`, `borderRight`, and `borderTop`. Preserve these values in the corresponding Unity Sprite importer metadata as `spriteBorder: {x: left, y: bottom, z: right, w: top}`. For Multiple-mode textures, write the border to the matching sprite entry rather than applying one border to the whole texture.

The script `scripts/convert_prefabs.py` performs both lookups automatically.

## Key Migration Rules

1. **Node Order Preservation**: Cocos `_children` array order must match Unity `m_Children` array order.
2. **RectTransform References**: Unity `m_Children` references RectTransform IDs, not GameObject IDs.
3. **CanvasRenderer**: Required for any node with Image or Text component.
4. **Image Type**: Set generated Images to Simple (`m_Type: 0`) except for sprites with a nine-slice border, which use Sliced (`m_Type: 1`), and a Slider's FillRect Image, which follows the Slider FillRect rule below.
5. **BestFit**: All Text components must have `m_BestFit: 1`.
6. **Font**: All Text components use Baloo2-Bold.
7. **Rich Text**: Generated Text components default to `m_RichText: 0`.
8. **Max Size**: Generated Text components set `m_MaxSize` to the same value as `m_FontSize`.
9. **Missing SpriteFrame**: If a Cocos `cc.Sprite` has no `_spriteFrame`, still generate the Unity `Image`, but set its color alpha to zero (`m_Color.a: 0`) so the image is invisible.
10. **Pivot and Anchors**: Map the Cocos node's `_anchorPoint.x` and `_anchorPoint.y` to Unity `RectTransform.m_Pivot`. Do not derive Unity anchors from the Cocos anchor point; keep `m_AnchorMin` and `m_AnchorMax` at their default centered values (`{x: 0.5, y: 0.5}`).
11. **Slider FillRect**: Set the FillRect Image to Filled (`m_Type: 3`) with Horizontal fill (`m_FillMethod: 0`). Stretch its RectTransform to its parent and inset every edge by 3 pixels: `m_AnchorMin: {x: 0, y: 0}`, `m_AnchorMax: {x: 1, y: 1}`, `m_OffsetMin: {x: 3, y: 3}`, and `m_OffsetMax: {x: -3, y: -3}`.
12. **Nine-Slice Images**: Preserve all four Cocos sprite border values during image migration. If any border is non-zero, the Unity Sprite importer must contain the mapped `spriteBorder`, and every generated `Image` that uses that sprite must be Sliced (`m_Type: 1`) unless it is a Slider FillRect, whose Filled type takes precedence.
13. **GridLayoutGroup CellSize**: Derived from first child node's `_contentSize`.
14. **Layout Type**: Cocos `layoutType=0` is NONE, `1` is HORIZONTAL, `2` is VERTICAL, `3` is GRID.

## Script Migration

See `references/script-migration.md` for detailed TS/JS to C# conversion patterns.

Quick reference:

| Cocos | Unity |
|---|---|
| `@ccclass` class | `MonoBehaviour` |
| `onLoad()` | `Awake()` / `Start()` |
| `update(dt)` | `Update()` (use `Time.deltaTime`) |
| `cc.instantiate()` | `Instantiate(prefab)` |
| `cc.find(path)` | `transform.Find(path)` |
| `cc.tween()` | `DOTween` (`DG.Tweening`) |
| `EventMgr.dispatch` | `MessageManager.Instance.SendMessage` |
| `LocalStorageMgr` | `CustomPrefesUtil` |
| `JSON.stringify/parse` | `JsonUtility.ToJson/FromJson` |

## Event System Migration

| Cocos (EventMgr) | Unity (MessageManager) |
|---|---|
| `EventMgr.dispatch("EVENT_NAME", data)` | `MessageManager.Instance.SendMessage("EVENT_NAME", data)` |
| `EventMgr.addEventListener("EVENT", handler, context)` | `MessageManager.Instance.RegisterMessage("EVENT", handler)` |
| `EventMgr.removeEventListener("EVENT", handler, context)` | `MessageManager.Instance.RemoveMessageListener("EVENT", handler)` |


## Usage

### Single Prefab Conversion

```bash
python scripts/convert_prefabs.py \\
  --input cocos_game_arrow/assets/subb/prefab/MyView.prefab \\
  --output unity_game_arrow/Assets/GameRes/Prefabs/MyView.prefab \\
  --cocos-sprites cocos_game_arrow/assets/subb/sprite \\
  --unity-textures unity_game_arrow/Assets/GameRes/Textures
```

### Batch Conversion

```bash
python scripts/convert_prefabs.py \\
  --batch \\
  --input cocos_game_arrow/assets/subb/prefab \\
  --output unity_game_arrow/Assets/GameRes/Prefabs \\
  --cocos-sprites cocos_game_arrow/assets/subb/sprite \\
  --unity-textures unity_game_arrow/Assets/GameRes/Textures
```

## Resources

- `scripts/convert_prefabs.py` - Main prefab migration script with CLI support
- `references/component-mapping.md` - Detailed component mapping with property tables and YAML examples
