# Script Migration Reference (Cocos TS/JS to Unity C#)

## Class Declaration

```ts
// Cocos
@property(cc.Node) btnSet: cc.Node = null;
this.btnSet = this.getChild("btnSet");
```
```csharp
// Unity
[SerializeField] private Transform btnSet;
this.btnSet = transform.Find("btnSet");
```

## Lifecycle Methods

| Cocos | Unity |
|---|---|
| `onLoad()` | `Awake()` / `Start()` |
| `start()` | `Start()` |
| `update(dt)` | `Update()` (use `Time.deltaTime`) |
| `onEnable()` | `OnEnable()` |
| `onDisable()` | `OnDisable()` |
| `onDestroy()` | `OnDestroy()` |

## Button Binding

```ts
// Cocos
this.btnSet.on("click", this.onClickBtnSet, this);
```
```csharp
// Unity
var button = btnSet.GetComponent<Button>();
button.onClick.AddListener(OnClickBtnSet);
```

项目 View 脚本应在 `OnViewAwake()` 注册事件，并在 `OnViewDestroy()` 移除事件。关闭窗口使用 `CloseView()`。框架会自动播放按钮点击音效，不要在点击回调中重复播放。

## Tween Animations

```ts
// Cocos
cc.tween(this.node).to(1.2, {x: maxX}).start();
```
```csharp
// Unity (DOTween)
this.transform.DOMoveX(maxX, 1.2f);
```

## Common API Mapping

| Cocos | Unity |
|---|---|
| `cc.Component` / `cc.Node` | `MonoBehaviour` + `Transform` |
| `cc.Sprite` | `UnityEngine.UI.Image` |
| `cc.Label` | `UnityEngine.UI.Text` |
| `cc.Button` | `UnityEngine.UI.Button` |
| `cc.Tween` / `cc.tween()` | `DOTween` (`DG.Tweening`) |
| `cc.Graphics` | `LineRenderer` / Custom Mesh |
| `cc.Node.on('click')` | `Button.onClick.AddListener()` |
| `cc.instantiate()` | `Instantiate(prefab)` |
| `cc.find(path)` | `transform.Find(path)` |
| `cc.Vec2` | `UnityEngine.Vector2` |
| `cc.Color` | `UnityEngine.Color` |
| `cc.Event.EventTouch` | `UnityEngine.EventSystems` |
| `cc.macro.REPEAT_FOREVER` | `InvokeRepeating` / Coroutine |

## Event System

| Cocos (EventMgr) | Unity (MessageManager) |
|---|---|
| `EventMgr.dispatch("EVENT_NAME", data)` | `MessageManager.Instance.SendMessage("EVENT_NAME", data)` |
| `EventMgr.addEventListener("EVENT", handler, context)` | `MessageManager.Instance.RegisterMessage("EVENT", handler)` |
| `EventMgr.removeEventListener("EVENT", handler, context)` | `MessageManager.Instance.RemoveMessageListener("EVENT", handler)` |

## Storage & Models

| Cocos (TS) | Unity (C#) |
|---|---|
| `LocalStorageMgr.getStringValue(key, default)` | `CustomPrefesUtil` 对应读取接口 |
| `LocalStorageMgr.setStringValue(key, value)` | `CustomPrefesUtil` 对应写入接口 |
| `LocalStorageMgr.getObject(key)` | `CustomPrefesUtil` + `JsonUtility.FromJson<T>()` |
| `JSON.stringify(obj)` / `JSON.parse(str)` | `JsonUtility.ToJson(obj)` / `JsonUtility.FromJson<T>(str)` |
| `EventMgr.dispatch(name, data)` | `MessageManager.Instance.SendMessage(name, data)` |

不要直接使用 `PlayerPrefs`。事件发布者和订阅者必须引用同一个 `GameEvent` 常量，避免仅大小写不同的重复事件名。

## Project Conventions

- 保留已有 Prefab 节点名；只有明确要求时才重命名。绑定代码应匹配实际层级，并在 `BindComponents()` 中使用 `?.` 保护可选节点。
- YooAsset 地址采用“父目录名_文件名”，例如 `Textures_icon_prop01`、`Sound_win`、`UI_PropView`。不要改用 `Resources.Load`。
- 项目异步代码使用 UniTask。`YooAssets.LoadAssetAsync<T>` 通过 `await handle.ToUniTask()` 等待；明确无需等待的 UniTask 调用以 `.Forget()` 结束。
- View 参数从 `OnShowView(ViewContextData data)` 的 `parameters` 数组读取。`ViewContextData` 构造函数最多传递三个参数。
- 文本必须在目标分辨率和安全区内检查，不能溢出或与相邻 UI 重叠。
