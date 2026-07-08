#nullable enable
using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using AntiLockScreen.Models;
using AntiLockScreen.Native;

namespace AntiLockScreen.Services;

/// <summary>
/// 后台防熄屏引擎（对应 Python _loop）。
/// API 模式调 SetThreadExecutionState；键盘/组合发 VK_F15；鼠标微移并「不抢操作」。
/// 间隔支持随机抖动（反检测），运行中可改模式/间隔。
/// </summary>
public sealed class AntiLockEngine : IDisposable
{
    private const uint ActiveFlags =
        NativeMethods.ES_CONTINUOUS | NativeMethods.ES_SYSTEM_REQUIRED | NativeMethods.ES_DISPLAY_REQUIRED;

    private static readonly int InputSize = Marshal.SizeOf<NativeMethods.INPUT>();

    private CancellationTokenSource? _cts;
    private Task? _task;
    private readonly Random _rnd = new();
    private NativeMethods.POINT? _lastMouse;

    public AppMode Mode { get; set; } = AppMode.Keyboard;
    public int Interval { get; set; } = 60;
    public bool Jitter { get; set; } = true;

    public bool IsRunning => _cts != null && !_cts.IsCancellationRequested;
    public DateTime LastTick { get; private set; } = DateTime.Now;
    public int DisplayInterval { get; private set; } = 60;
    public DateTime? SessionStart { get; private set; }

    public event Action? StateChanged;

    public void Start()
    {
        if (IsRunning) return;
        _cts = new CancellationTokenSource();
        if (Mode == AppMode.Api || Mode == AppMode.Hybrid)
            NativeMethods.SetThreadExecutionState(ActiveFlags);
        SessionStart = DateTime.Now;
        LastTick = DateTime.Now;
        DisplayInterval = Math.Max(1, Interval);
        _lastMouse = null;
        var token = _cts.Token;
        _task = Task.Run(() => Loop(token));
        StateChanged?.Invoke();
    }

    public void Stop()
    {
        if (!IsRunning) return;
        try { _cts?.Cancel(); } catch { /* ignore */ }
        _cts = null;
        NativeMethods.SetThreadExecutionState(NativeMethods.ES_CONTINUOUS);
        SessionStart = null;
        StateChanged?.Invoke();
    }

    /// <summary>运行中切换模式后，按新模式刷新 API 防熄屏状态（对应 Python _select_mode 里的 api_clear/api_set）。</summary>
    public void RefreshApiState()
    {
        if (!IsRunning) return;
        if (Mode == AppMode.Api || Mode == AppMode.Hybrid)
            NativeMethods.SetThreadExecutionState(ActiveFlags);
        else
            NativeMethods.SetThreadExecutionState(NativeMethods.ES_CONTINUOUS);
    }

    private async Task Loop(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try { PerformInput(); } catch { /* swallow per-tick errors */ }
            LastTick = DateTime.Now;
            var iv = Math.Max(1, Interval);
            if (Jitter) iv = Math.Max(5, (int)(iv * (_rnd.NextDouble() * 0.4 + 0.8)));
            DisplayInterval = iv;
            try { await Task.Delay(iv * 1000, ct); }
            catch (TaskCanceledException) { break; }
        }
    }

    private void PerformInput()
    {
        switch (Mode)
        {
            case AppMode.Keyboard:
            case AppMode.Hybrid:
                PressKey(NativeMethods.VK_F15);
                break;
            case AppMode.Mouse:
                if (NativeMethods.GetCursorPos(out var p))
                {
                    if (_lastMouse is null || (_lastMouse.Value.X == p.X && _lastMouse.Value.Y == p.Y))
                        MouseJiggle(1, 1);
                    _lastMouse = p;
                }
                break;
        }
    }

    private static void PressKey(ushort vk)
    {
        var down = new NativeMethods.INPUT
        {
            type = NativeMethods.INPUT_KEYBOARD,
            u = new NativeMethods.INPUT_UNION
            {
                ki = new NativeMethods.KEYBDINPUT { wVk = vk },
            },
        };
        var up = new NativeMethods.INPUT
        {
            type = NativeMethods.INPUT_KEYBOARD,
            u = new NativeMethods.INPUT_UNION
            {
                ki = new NativeMethods.KEYBDINPUT { wVk = vk, dwFlags = NativeMethods.KEYEVENTF_KEYUP },
            },
        };
        NativeMethods.SendInput(2, new[] { down, up }, InputSize);
    }

    private static void MouseJiggle(int dx, int dy)
    {
        for (int i = 0; i < 2; i++)
        {
            var inp = new NativeMethods.INPUT
            {
                type = NativeMethods.INPUT_MOUSE,
                u = new NativeMethods.INPUT_UNION
                {
                    mi = new NativeMethods.MOUSEINPUT
                    {
                        dx = i == 0 ? dx : -dx,
                        dy = i == 0 ? dy : -dy,
                        dwFlags = NativeMethods.MOUSEEVENTF_MOVE,
                    },
                },
            };
            NativeMethods.SendInput(1, new[] { inp }, InputSize);
            Thread.Sleep(20);
        }
    }

    public void Dispose() => Stop();
}
