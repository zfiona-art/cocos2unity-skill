---
name: cocos-to-unity-script
description: >
  Migrate Cocos Creator TypeScript/JavaScript game-logic scripts to Unity C#.
  Use when:
  - Porting Cocos TS/JS game logic scripts to Unity C#
  - Migrating Cocos event system (EventMgr) to Unity MessageManager
  - Porting Cocos Model layer to C#
  - Converting Cocos lifecycle methods (onLoad/start/update) to Unity MonoBehaviour lifecycle
  - Replacing cc.tween() animations with DOTween
  - Replacing LocalStorageMgr with CustomPrefesUtil
---

# Cocos to Unity Script Migration

## Overview

Convert Cocos Creator TypeScript/JavaScript game-logic scripts to Unity C#, following the project's View framework conventions (OnViewAwake/OnViewDestroy/CloseView, MessageManager, YooAsset, UniTask).

## Quick Reference

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

## Resources

- `references/script-migration.md` - Detailed TS/JS to C# conversion patterns and project conventions
