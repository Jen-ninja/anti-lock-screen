#nullable enable
using System;
using System.Collections.Generic;
using AntiLockScreen.Native;

namespace AntiLockScreen.Services;

/// <summary>
/// 全局热键管理（对应 Python HotkeyListener）。
/// 用窗口句柄 RegisterHotKey，WM_HOTKEY 经窗口 WndProc 分发 → HandleMessage。
/// </summary>
public sealed class GlobalHotkeyManager : IDisposable
{
    private readonly IntPtr _hwnd;
    private readonly Dictionary<int, Action> _map = new();

    /// <summary>每个 id 是否注册成功（用于「可能被占用」提示）。</summary>
    public Dictionary<int, bool> Ok { get; } = new();

    public GlobalHotkeyManager(IntPtr hwnd) => _hwnd = hwnd;

    public void Set(IEnumerable<(int id, uint mods, uint vk, Action cb)> entries)
    {
        Clear();
        Ok.Clear();
        foreach (var (id, mods, vk, cb) in entries)
        {
            // MOD_NOREPEAT：长按不重复触发（Python 未设；此处为体验改进，单击行为不变）
            var ok = NativeMethods.RegisterHotKey(_hwnd, id, mods | NativeMethods.MOD_NOREPEAT, vk);
            if (ok) _map[id] = cb;
            Ok[id] = ok;
        }
    }

    public void Clear()
    {
        foreach (var id in new List<int>(_map.Keys))
        {
            try { NativeMethods.UnregisterHotKey(_hwnd, id); } catch { /* ignore */ }
        }
        _map.Clear();
    }

    /// <summary>窗口 WndProc 调用；返回是否已处理该消息。</summary>
    public bool HandleMessage(uint msg, IntPtr wParam)
    {
        if (msg != NativeMethods.WM_HOTKEY) return false;
        int id = wParam.ToInt32();
        if (_map.TryGetValue(id, out var cb))
        {
            try { cb(); } catch { /* swallow */ }
            return true;
        }
        return false;
    }

    public void Dispose() => Clear();
}
