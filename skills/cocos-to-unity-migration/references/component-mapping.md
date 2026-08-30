# Component Mapping Reference

## Cocos to Unity Component Mapping

### Rendering Components

| Cocos | Unity | GUID | Properties |
|---|---|---|---|
| `cc.Sprite` | `Image` (MonoBehaviour) | `fe87c0e1cc204ed48ad3b37840f39efc` | `m_Sprite`, `m_Type: 0`, `m_Color` |
| `cc.Label` | `Text` (MonoBehaviour) | `5f7201a12d95ffc409449d95f23cf332` | `m_Text`, `m_FontSize`, `m_BestFit: 1`, `m_MaxSize = m_FontSize`, `m_RichText: 0`, `m_FontData.m_Font` |
| `cc.LabelOutline` | `Outline` (MonoBehaviour) | `e19747de3f5aca642ab2be37e372fb86` | `m_EffectColor`, `m_EffectDistance` |

### Input Components

| Cocos | Unity | GUID | Properties |
|---|---|---|---|
| `cc.Button` | `Button` (MonoBehaviour) | `4e29b1a8efbd4b44bb3f3716e73f07ff` | `m_Transition`, `m_Colors`, `m_OnClick` |
| `cc.EditBox` | `InputField` (MonoBehaviour) | `d199490a83bb2b844b9695cbf13b01ef` | Input field properties |

### Layout Components

| Cocos | Unity | GUID | Properties |
|---|---|---|---|
| `cc.Layout` (type=0) | `HorizontalLayoutGroup` | `30649d3a9faa99c48a7b1166b86bf2a0` | `m_Padding`, `m_Spacing`, `m_ChildForceExpandWidth` |
| `cc.Layout` (type=2) | `VerticalLayoutGroup` | `59f8146938fff824cb5fd77236b75775` | `m_Padding`, `m_Spacing`, `m_ChildForceExpandWidth` |
| `cc.Layout` (type=3) | `GridLayoutGroup` | `8a8695521f0d02e499659fee002a26c2` | `m_Padding`, `m_CellSize`, `m_Spacing`, `m_Constraint` |

### Other Components

| Cocos | Unity | GUID | Properties |
|---|---|---|---|
| `cc.ScrollView` | `ScrollRect` (MonoBehaviour) | `1aa08ab6e0800fa44ae55d278d1423e3` | `m_Content`, `m_Horizontal`, `m_Vertical`, `m_MovementType` |
| `cc.ProgressBar` | `Slider` (MonoBehaviour) | `67db9e8f0e2ae9c40bc1e2b64352a6b4` | Progress bar properties |
| `cc.Slider` | `Slider` (MonoBehaviour) | `67db9e8f0e2ae9c40bc1e2b64352a6b4` | Slider properties |
| `cc.Mask` | `RectMask2D` (MonoBehaviour) | `3312d7739989d2b4e91e6319e9a96d76` | Rectangular clipping |

## Node Structure Mapping

### Cocos Node Structure
```json
{
  "__type__": "cc.Node",
  "_name": "NodeName",
  "_parent": null,
  "_children": [{"__id__": 2}],
  "_components": [{"__id__": 3}],
  "_trs": {"array": [x, y, z, 0, 0, 0, 1, sx, sy, sz]},
  "_contentSize": {"width": 100, "height": 100},
  "_anchorPoint": {"x": 0.5, "y": 0.5}
}
```

### Unity Counterpart
```yaml
--- !u!1 &<fileID>
GameObject:
  m_Name: NodeName
  m_Component:
  - component: {fileID: <trans_id>}
  - component: {fileID: <comp_id>}

--- !u!224 &<trans_id>
RectTransform:
  m_GameObject: {fileID: <go_id>}
  m_LocalPosition: {x: <x>, y: <y>, z: <z>}
  m_LocalScale: {x: <sx>, y: <sy>, z: <sz>}
  m_SizeDelta: {x: <width>, y: <height>}
  m_Pivot: {x: <ax>, y: <ay>}
```

## Sprite Reference Resolution

### Step 1: Extract Cocos UUID
```json
"_spriteFrame": {
  "__uuid__": "db63661f-f837-48da-9181-cd7468374ced"
}
```

### Step 2: Map to Filename
Read Cocos `.meta` file from `cocos_game_arrow/assets/subb/sprite/*.png.meta`:
```json
{
  "subMetas": {
    "cell_sign_nor": {
      "uuid": "db63661f-f837-48da-9181-cd7468374ced"
    }
  }
}
```
Filename: `cell_sign_nor.png`

### Step 3: Map to Unity GUID
Read Unity `.meta` file from `unity_game_arrow/Assets/GameRes/Textures/cell_sign_nor.png.meta`:
```
guid: 73e65ffbe283441ca9c44a184f6715bc
```

### Step 4: Write Unity Reference
```yaml
m_Sprite: {fileID: 21300000, guid: 73e65ffbe283441ca9c44a184f6715bc, type: 3}
```

## Common Pitfalls

1. **Wrong GUID for VerticalLayoutGroup**: Unity version-specific GUIDs may differ. Verify against existing prefabs in the project.
2. **m_Children references GameObject instead of RectTransform**: Unity `m_Children` must reference `RectTransform` fileIDs, not `GameObject` fileIDs.
3. **Missing CanvasRenderer**: Nodes with Image or Text components need a CanvasRenderer component.
4. **LayoutType mapping**: Cocos `layoutType=0` is NONE, `1` is HORIZONTAL, `2` is VERTICAL, `3` is GRID.
