#nullable enable
using System;
using System.Runtime.InteropServices;
using AntiLockScreen.Native;

namespace AntiLockScreen.Services;

/// <summary>
/// 系统托盘（对应 Python _make_tray + pystray）。
/// 纯 P/Invoke：Shell_NotifyIconW + Win32 弹出菜单，零第三方依赖。
/// 左键单击/双击 = 显隐窗口；右键 = 菜单。
/// </summary>
public sealed class TrayIconController : IDisposable
{
    private const uint TrayId = 1;
    private const uint CmdToggleVis = 1001;
    private const uint CmdToggleRun = 1002;
    private const uint CmdReset = 1003;
    private const uint CmdQuit = 1004;

    private IntPtr _hwnd = IntPtr.Zero;
    private IntPtr _hIcon = IntPtr.Zero;
    private bool _added;

    public Action? OnToggleVisibility;
    public Action? OnToggleRunning;
    public Action? OnReset;
    public Action? OnQuit;
    public Func<bool> IsRunning { get; set; } = () => false;

    private static NativeMethods.NOTIFYICONDATAW BuildData(IntPtr hwnd, IntPtr icon, string tip)
    {
        return new NativeMethods.NOTIFYICONDATAW
        {
            cbSize = (uint)Marshal.SizeOf<NativeMethods.NOTIFYICONDATAW>(),
            hWnd = hwnd,
            uID = TrayId,
            uFlags = NativeMethods.NIF_MESSAGE | NativeMethods.NIF_ICON | NativeMethods.NIF_TIP,
            uCallbackMessage = NativeMethods.WM_APP_TRAY,
            hIcon = icon,
            szTip = tip ?? "",
            szInfo = "",
            szInfoTitle = "",
        };
    }

    public void Init(IntPtr hwnd, IntPtr hIcon, string tip)
    {
        _hwnd = hwnd;
        _hIcon = hIcon;
        var d = BuildData(hwnd, _hIcon, tip);
        _added = NativeMethods.Shell_NotifyIconW(NativeMethods.NIM_ADD, ref d);
    }

    public void ShowBalloon(string title, string message)
    {
        if (!_added) return;
        var d = BuildData(_hwnd, _hIcon, "防熄屏");
        d.uFlags = NativeMethods.NIF_INFO | NativeMethods.NIF_ICON | NativeMethods.NIF_MESSAGE;
        d.szInfo = message ?? "";
        d.szInfoTitle = title ?? "";
        d.dwInfoFlags = NativeMethods.NIIF_INFO;
        NativeMethods.Shell_NotifyIconW(NativeMethods.NIM_MODIFY, ref d);
    }

    /// <summary>窗口 WndProc 调用；处理托盘鼠标消息。</summary>
    public bool HandleMessage(uint msg, IntPtr wParam, IntPtr lParam)
    {
        if (msg != NativeMethods.WM_APP_TRAY) return false;
        uint mouse = (uint)(lParam.ToInt64() & 0xFFFF);
        switch (mouse)
        {
            case NativeMethods.WM_LBUTTONUP:
            case NativeMethods.WM_LBUTTONDBLCLK:
                OnToggleVisibility?.Invoke();
                return true;
            case NativeMethods.WM_RBUTTONUP:
                ShowContextMenu();
                return true;
        }
        return false;
    }

    private void ShowContextMenu()
    {
        var hMenu = NativeMethods.CreatePopupMenu();
        if (hMenu == IntPtr.Zero) return;
        try
        {
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_STRING, (nuint)CmdToggleVis, "显示 / 隐藏窗口");
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_SEPARATOR, (nuint)0, null);
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_STRING, (nuint)CmdToggleRun,
                IsRunning() ? "停止防锁屏" : "开启防锁屏");
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_SEPARATOR, (nuint)0, null);
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_STRING, (nuint)CmdReset, "恢复默认设置");
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_SEPARATOR, (nuint)0, null);
            NativeMethods.AppendMenuW(hMenu, NativeMethods.MF_STRING, (nuint)CmdQuit, "退出");

            NativeMethods.GetCursorPos(out var p);
            // SetForegroundWindow + PostMessage(WM_NULL)：修复菜单点击后不自动消失的 Win32 已知行为
            NativeMethods.SetForegroundWindow(_hwnd);
            var cmdRaw = NativeMethods.TrackPopupMenuEx(hMenu,
                NativeMethods.TPM_RIGHTALIGN | NativeMethods.TPM_BOTTOMALIGN |
                NativeMethods.TPM_RETURNCMD | NativeMethods.TPM_NONOTIFY,
                p.X, p.Y, _hwnd, IntPtr.Zero);
            NativeMethods.PostMessage(_hwnd, NativeMethods.WM_NULL, IntPtr.Zero, IntPtr.Zero);

            switch ((uint)cmdRaw)
            {
                case CmdToggleVis: OnToggleVisibility?.Invoke(); break;
                case CmdToggleRun: OnToggleRunning?.Invoke(); break;
                case CmdReset: OnReset?.Invoke(); break;
                case CmdQuit: OnQuit?.Invoke(); break;
            }
        }
        finally
        {
            NativeMethods.DestroyMenu(hMenu);
        }
    }

    public void Dispose()
    {
        if (_added)
        {
            var d = BuildData(_hwnd, _hIcon, "");
            NativeMethods.Shell_NotifyIconW(NativeMethods.NIM_DELETE, ref d);
            _added = false;
        }
        // 托盘图标 HICON 由外部（MainWindow 的 System.Drawing.Icon）持有，此处不销毁
        _hIcon = IntPtr.Zero;
    }
}
