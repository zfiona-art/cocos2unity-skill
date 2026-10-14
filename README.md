# cocos2unity-skill

用于将 Cocos Creator 项目迁移到 Unity 的 Codex 技能集合，包含 UI Prefab 转换工具和 TypeScript / JavaScript 游戏逻辑迁移指引。

## 目录结构

```text
skills/
├── cocos-to-unity-prefab/
│   ├── SKILL.md                       # Prefab 迁移规则与操作说明
│   ├── scripts/convert_prefabs.py      # JSON Prefab → Unity YAML Prefab
│   └── references/component-mapping.md
└── cocos-to-unity-script/
    ├── SKILL.md                       # TS / JS → C# 迁移指引
    └── references/script-migration.md
```

## 安装与使用技能

将 `skills` 下的两个技能目录复制到本机 Codex 技能目录。以下命令在本仓库根目录执行，适用于 macOS / Linux：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/cocos-to-unity-prefab "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R skills/cocos-to-unity-script "${CODEX_HOME:-$HOME/.codex}/skills/"
```

如果已有同名技能，先确认是否需要更新其内容。安装后在新的 Codex 会话中明确指定技能，并提供源项目、目标项目和迁移范围，例如：

```text
使用 $cocos-to-unity-prefab，将 /path/to/cocos/assets/prefab/MyView.prefab
转换到 /path/to/unity/Assets/GameRes/Prefabs/MyView.prefab。
Cocos 图片目录为 /path/to/cocos/assets/sprite，
Unity 图片目录为 /path/to/unity/Assets/GameRes/Textures。
```

```text
使用 $cocos-to-unity-script，将 /path/to/cocos/assets/scripts/MyView.ts
迁移到 /path/to/unity/Assets/Scripts/MyView.cs，参考目标项目已有的
View 基类、消息系统、资源加载和存储接口，并保留原有行为。
```

脚本迁移技能提供规则和参考示例，由代理结合目标项目实施；本仓库没有 TS / JS 一键转 C# 的转换器。

## 直接运行 Prefab 转换工具

### 准备工作

- 安装 Python 3；转换器仅使用 Python 标准库，无需安装额外依赖。
- 准备 Cocos Creator 的 JSON 格式 `.prefab`，以及图片对应的 `.meta` 文件。转换器按 `cc.Node`、`cc.Sprite` 等序列化结构解析；其他版本或结构需先核对兼容性。
- 先将图片复制到 Unity 项目，并在 Unity 中导入为 Sprite，生成 `.meta`。转换器读取已有图片 GUID，不负责复制图片或配置全部导入设置。
- 当前字体固定引用 Baloo2-Bold，GUID 为 `1f61a3045ca384d658e06ced93fe9bc9`。目标项目应包含对应字体资产，或按实际字体修改转换器中的 `GUID_FONT`。
- 以下命令均在本仓库根目录执行。将示例中的 `/path/to/...` 替换为实际路径。

### 单个 Prefab

先确保输出文件的父目录存在：

```bash
mkdir -p /path/to/unity/Assets/GameRes/Prefabs

python3 skills/cocos-to-unity-prefab/scripts/convert_prefabs.py \
  --input /path/to/cocos/assets/prefab/MyView.prefab \
  --output /path/to/unity/Assets/GameRes/Prefabs/MyView.prefab \
  --cocos-sprites /path/to/cocos/assets/sprite \
  --unity-textures /path/to/unity/Assets/GameRes/Textures
```

### 批量转换

递归扫描输入目录中的 `.prefab`，输出目录会自动创建：

```bash
python3 skills/cocos-to-unity-prefab/scripts/convert_prefabs.py \
  --batch \
  --input /path/to/cocos/assets/prefab \
  --output /path/to/unity/Assets/GameRes/Prefabs \
  --cocos-sprites /path/to/cocos/assets/sprite \
  --unity-textures /path/to/unity/Assets/GameRes/Textures
```

批量输出会集中到同一目录，不保留源目录层级。不同子目录中的同名 Prefab 会写入同一个输出文件；运行前应检查重名情况。已有输出文件也会被覆盖。

### 参数说明

| 参数 | 说明 |
| --- | --- |
| `--input` / `-i` | 必填。单文件模式传入源 Prefab，批量模式传入源目录。 |
| `--output` / `-o` | 必填。单文件模式传入输出 Prefab，批量模式传入输出目录。 |
| `--cocos-sprites` | Cocos 图片与 `.meta` 所在目录，用于 UUID 解析。建议显式指定。 |
| `--unity-textures` | Unity 图片与 `.meta` 所在目录，用于 GUID 解析及九宫格边框写入。建议显式指定。 |
| `--batch` / `-b` | 启用批量转换。 |
| `--prefix-module` | 匹配按顶层模块名添加前缀的 Unity 图片，例如 `common/icon.png` 对应 `common_icon.png`；`spine` 目录不添加前缀。 |
| `--unity-scripts` | 扫描 Unity C# 脚本及 `.cs.meta`，挂载与源 Prefab 文件名同名的类。 |
| `--skip-borders` | 跳过向 Unity 图片 `.meta` 写入九宫格边框；仍会依据 Cocos 边框信息选择 Image 类型。 |
| `--help` / `-h` | 查看命令行帮助。 |

例如，在普通转换命令后追加以下参数，可查找并挂载同名 View 脚本：

```text
--unity-scripts /path/to/unity/Assets/Scripts
```

## 转换行为与检查

主要组件映射如下，详细属性见 [组件映射参考](skills/cocos-to-unity-prefab/references/component-mapping.md)。

| Cocos | Unity UGUI |
| --- | --- |
| `cc.Sprite` | `Image` |
| `cc.Label` / `cc.LabelOutline` | `Text` / `Outline` |
| `cc.Button` | `Button` |
| `cc.Layout` | `HorizontalLayoutGroup` / `VerticalLayoutGroup` / `GridLayoutGroup` |
| `cc.ScrollView` | `ScrollRect` |
| `cc.ProgressBar` / `cc.Slider` | `Slider` |
| `cc.EditBox` | `InputField` |
| `cc.Mask` | `RectMask2D` |

- 保留节点层级、子节点顺序及主要变换信息。Cocos 锚点映射到 Unity Pivot，Unity anchors 默认居中。
- 图片引用通过 Cocos UUID → 图片文件名 → Unity GUID 解析。同名图片存在歧义时应先整理资源；当前工具不会主动拒绝重名映射。
- 默认将非零九宫格边框写入目标图片 `.meta`，并将对应 Image 设置为 Sliced。此操作会修改传入的 Unity 图片目录，建议通过版本控制检查差异。
- Slider FillRect 使用 Filled / Horizontal，并按规则拉伸、向内缩进 3 像素。
- 文本使用传统 UGUI `Text`，开启 BestFit，关闭 Rich Text；没有 SpriteFrame 的 Sprite 仍生成 Image，但透明度设为零。
- 自定义业务脚本、事件回调和未支持的组件需另外迁移；生成 YAML 不代表交互逻辑已完整恢复。

转换后在 Unity 中等待资源导入，打开 Prefab 检查 Missing Script、图片和字体引用、布局、九宫格、滚动区域与输入控件，再在目标分辨率下验证交互。批量模式应检查每条 `[FAIL]` / `[ERR]` 以及最终成功数量。

## C# 脚本迁移约定

[脚本迁移参考](skills/cocos-to-unity-script/references/script-migration.md) 包含生命周期、按钮绑定、动画、事件、存储与 Model 层迁移示例：

- `cc.tween()` 对应 DOTween，`EventMgr` 对应目标项目的 `MessageManager`。
- 遵循目标 View 框架的 `OnViewAwake()`、`OnViewDestroy()`、`CloseView()` 等约定。
- 资源加载、异步与存储示例分别基于 YooAsset、UniTask、`CustomPrefesUtil`；迁移前确认目标项目实际接口和依赖。
- 保留 Prefab 节点名称，绑定代码匹配实际层级，事件发布与订阅使用一致的常量。
- 新建或修改 `.cs` 文件统一保存为 UTF-8 **带 BOM**；修改已有脚本时保留原换行风格，避免无关格式变更。脚本生成器也应显式使用带 BOM 的 UTF-8 编码。

最终应在目标 Unity 项目中完成编译和运行验证。
