#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;
using AntiLockScreen.Models;
using AntiLockScreen.Native;
using AntiLockScreen.Services;

namespace AntiLockScreen;

public partial class MainWindow : Window
{
    private const int HkIdShow = 1;
    private const int HkIdRun = 2;
    private const double EdgeMargin = 8;
    private const double FullW = 300, FullH = 488;
    private const double MiniW = 80, MiniH = 80;

    private readonly AntiLockEngine _engine = new();
    private AppConfig _cfg = AppConfig.Default();
    private GlobalHotkeyManager? _hotkey;
    private readonly TrayIconController _tray = new();
    private System.Drawing.Icon _appIcon = System.Drawing.SystemIcons.Application;

    private bool _loading = true;
    private bool _visible = true;
    private bool _cleaned;

    // 热键捕获
    private bool _capturing;
    private string? _captureTarget;

    // mini 台灯拖动/单击区分
    private bool _lampDragStarted;
    private Point _lampDownPos;

    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromMilliseconds(250) };

    public MainWindow()
    {
        InitializeComponent();
        _cfg = ConfigStore.Load();

        // 绑定引擎参数
        _engine.Mode = _cfg.ModeEnum;
        _engine.Interval = Math.Max(1, _cfg.Interval);
        _engine.Jitter = _cfg.Jitter;
        _engine.StateChanged += () => Dispatcher.BeginInvoke(new Action(UpdateRunUi));

        ApplyUiFromConfig();

        _timer.Tick += (_, _) => RefreshStatus();
        _timer.Start();
        _loading = false;
    }

    // ---------- 初始化（需要窗口句柄） ----------
    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        var helper = new WindowInteropHelper(this);
        var hwnd = helper.Handle;
        HwndSource.FromHwnd(hwnd)?.AddHook(WndProc);

        // 初始位置：屏幕右上
        var sw = SystemParameters.PrimaryScreenWidth;
        Left = sw - FullW - 20;
        Top = 80;

        // 托盘
        _appIcon = LoadAppIcon();
        _tray.IsRunning = () => _engine.IsRunning;
        _tray.OnToggleVisibility = ToggleVisibility;
        _tray.OnToggleRunning = Toggle;
        _tray.OnReset = ResetDefaults;
        _tray.OnQuit = Quit;
        _tray.Init(hwnd, _appIcon.Handle, "防熄屏");

        // 全局热键
        _hotkey = new GlobalHotkeyManager(hwnd);
        ApplyHotkeys();

        // 启动即开启
        if (_cfg.AutoOn)
            Dispatcher.BeginInvoke(new Action(() => { Start(); }), DispatcherPriority.ApplicationIdle);
    }

    private System.Drawing.Icon LoadAppIcon()
    {
        try
        {
            var asm = Assembly.GetExecutingAssembly();
            var name = asm.GetManifestResourceNames().FirstOrDefault(n => n.EndsWith("app.ico", StringComparison.OrdinalIgnoreCase));
            if (name != null)
            {
                using var s = asm.GetManifestResourceStream(name);
                if (s != null) return new System.Drawing.Icon(s);
            }
        }
        catch { /* ignore */ }
        return System.Drawing.SystemIcons.Application;
    }

    // ---------- WndProc：热键 + 托盘消息分发 ----------
    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        uint m = (uint)msg;
        if (_hotkey != null && _hotkey.HandleMessage(m, wParam))
            handled = true;
        else if (_tray.HandleMessage(m, wParam, lParam))
            handled = true;
        return IntPtr.Zero;
    }

    // ---------- UI 同步 ----------
    private void ApplyUiFromConfig()
    {
        _loading = true;
        IntervalBox.Text = Math.Max(1, _cfg.Interval).ToString();
        ChipKeyboard.IsChecked = _cfg.ModeEnum == AppMode.Keyboard;
        ChipMouse.IsChecked = _cfg.ModeEnum == AppMode.Mouse;
        ChipApi.IsChecked = _cfg.ModeEnum == AppMode.Api;
        ChipHybrid.IsChecked = _cfg.ModeEnum == AppMode.Hybrid;
        SwAutoon.IsChecked = _cfg.AutoOn;
        SwJitter.IsChecked = _cfg.Jitter;
        SwNotify.IsChecked = _cfg.Notify;
        SwAutostart.IsChecked = Autostart.IsEnabled();
        HkShowBtn.Content = _cfg.Hotkeys.Show.Label;
        HkRunBtn.Content = _cfg.Hotkeys.Run.Label;
        _loading = false;
    }

    private void UpdateRunUi()
    {
        bool run = _engine.IsRunning;
        ToggleBtn.Content = run ? "停止防锁屏" : "开启防锁屏";
        ToggleBtn.Background = (Brush)(run ? FindResource("Red") : FindResource("Accent"));
        LampMini.IsOn = run;
        StatusDot.Fill = (Brush)(run ? FindResource("Accent") : FindResource("DotOff"));
    }

    private void RefreshStatus()
    {
        if (_engine.IsRunning)
        {
            var remain = Math.Max(0, _engine.DisplayInterval - (DateTime.Now - _engine.LastTick).TotalSeconds);
            var elapsed = DateTime.Now - (_engine.SessionStart ?? DateTime.Now);
            StatusLabel.Text = $"⏱ 已运行 {FmtDur(elapsed.TotalSeconds)} · 下次 {remain:F0}s";
        }
        else if (_cfg.LastSession is double ls && ls > 0)
        {
            StatusLabel.Text = $"已停止 · 上次 {FmtDur(ls)} · {_cfg.Hotkeys.Run.Label} 开启";
        }
        else
        {
            StatusLabel.Text = $"已停止 · {_cfg.Hotkeys.Run.Label} 开启";
        }
        UpdateRunUi();
    }

    // ---------- 自适应尺寸（移植 Python _resize） ----------
    private void ResizeWithLayout(double w, double h)
    {
        double x = Left, y = Top;
        double curW = Width, curH = Height;
        double sw = SystemParameters.PrimaryScreenWidth;
        double sh = SystemParameters.PrimaryScreenHeight;
        // 向右/下展开会超出屏幕时，改为右/下边缘对齐（向反方向展开）
        if (x + w > sw - EdgeMargin) x = x + curW - w;
        if (y + h > sh - EdgeMargin) y = y + curH - h;
        // 夹回屏幕内
        x = Math.Min(Math.Max(EdgeMargin, x), Math.Max(EdgeMargin, sw - w - EdgeMargin));
        y = Math.Min(Math.Max(EdgeMargin, y), Math.Max(EdgeMargin, sh - h - EdgeMargin));
        Width = w;
        Height = h;
        Left = x;
        Top = y;
    }

    // ---------- mini / full 切换 ----------
    private void EnterMini()
    {
        FullCard.Visibility = Visibility.Collapsed;
        MiniLamp.Visibility = Visibility.Visible;
        ResizeWithLayout(MiniW, MiniH);
        _visible = true;
        UpdateRunUi();
    }

    private void ExitMini()
    {
        MiniLamp.Visibility = Visibility.Collapsed;
        FullCard.Visibility = Visibility.Visible;
        ResizeWithLayout(FullW, FullH);
        _visible = true;
        Topmost = true;
    }

    // ---------- 标题栏拖动 ----------
    private void Header_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
            DragMove();
    }

    // ---------- mini 台灯：拖动 + 单击开关 + 右键还原 ----------
    private void Lamp_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton != MouseButton.Left) return;
        _lampDragStarted = false;
        _lampDownPos = e.GetPosition(this);
    }

    private void Lamp_MouseMove(object sender, MouseEventArgs e)
    {
        if (e.LeftButton != MouseButtonState.Pressed || _lampDragStarted) return;
        var p = e.GetPosition(this);
        double dx = Math.Abs(p.X - _lampDownPos.X);
        double dy = Math.Abs(p.Y - _lampDownPos.Y);
        if (dx > SystemParameters.MinimumHorizontalDragDistance ||
            dy > SystemParameters.MinimumVerticalDragDistance)
        {
            _lampDragStarted = true;
            DragMove();
        }
    }

    private void Lamp_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (!_lampDragStarted)
            Toggle();
    }

    private void Lamp_RightMouseUp(object sender, MouseButtonEventArgs e)
    {
        ExitMini();
    }

    // ---------- 标题栏按钮 ----------
    private void BtnClose_Click(object sender, RoutedEventArgs e) => Quit();
    private void BtnMinimize_Click(object sender, RoutedEventArgs e) => HideToTray();
    private void BtnShrink_Click(object sender, RoutedEventArgs e) => EnterMini();

    // ---------- 开关 ----------
    private void ToggleBtn_Click(object sender, RoutedEventArgs e) => Toggle();

    public void Toggle()
    {
        if (_engine.IsRunning) Stop();
        else Start();
    }

    private void Start()
    {
        if (!int.TryParse(IntervalBox.Text, out var iv) || iv < 1) { iv = 60; IntervalBox.Text = "60"; }
        _cfg.Interval = iv;
        _engine.Interval = Math.Max(1, iv);
        _engine.Mode = _cfg.ModeEnum;
        _engine.Jitter = _cfg.Jitter;
        _engine.Start();
        Notify(true);
        SaveCfg();
    }

    private void Stop()
    {
        if (_engine.SessionStart is DateTime s)
        {
            _cfg.LastSession = (DateTime.Now - s).TotalSeconds;
            SaveCfg();
        }
        _engine.Stop();
        Notify(false);
    }

    private void Notify(bool running)
    {
        if (!_cfg.Notify) return;
        try { _tray.ShowBalloon("防熄屏", running ? $"已开启 · {AppModes.Label(_engine.Mode)}" : "已停止"); }
        catch { /* ignore */ }
        try { Console.Beep(running ? 880 : 620, 140); }
        catch { /* ignore */ }
    }

    // ---------- 模式 ----------
    private void Chip_Click(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        if (sender == ChipKeyboard) _cfg.Mode = AppModes.ToConfig(AppMode.Keyboard);
        else if (sender == ChipMouse) _cfg.Mode = AppModes.ToConfig(AppMode.Mouse);
        else if (sender == ChipApi) _cfg.Mode = AppModes.ToConfig(AppMode.Api);
        else if (sender == ChipHybrid) _cfg.Mode = AppModes.ToConfig(AppMode.Hybrid);
        _engine.Mode = _cfg.ModeEnum;
        _engine.RefreshApiState();
        SaveCfg();
    }

    // ---------- 间隔 ----------
    private void IntervalBox_PreviewTextInput(object sender, TextCompositionEventArgs e)
        => e.Handled = !e.Text.All(char.IsDigit);

    private void IntervalBox_Pasting(object sender, DataObjectPastingEventArgs e)
    {
        if (e.DataObject.GetDataPresent(typeof(string)))
        {
            var s = (string)e.DataObject.GetData(typeof(string));
            if (!s.All(char.IsDigit)) e.CancelCommand();
        }
        else e.CancelCommand();
    }

    private void IntervalBox_TextChanged(object sender, System.Windows.Controls.TextChangedEventArgs e)
    {
        if (_loading) return;
        if (int.TryParse(IntervalBox.Text, out var v) && v >= 1)
        {
            _cfg.Interval = v;
            _engine.Interval = v;
            SaveCfg();
        }
    }

    // ---------- 设置开关 ----------
    private void SwAutostart_Changed(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        Autostart.Set(SwAutostart.IsChecked == true);
    }

    private void SwBool_Changed(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        if (sender == SwAutoon) _cfg.AutoOn = SwAutoon.IsChecked == true;
        else if (sender == SwJitter) { _cfg.Jitter = SwJitter.IsChecked == true; _engine.Jitter = _cfg.Jitter; }
        else if (sender == SwNotify) _cfg.Notify = SwNotify.IsChecked == true;
        SaveCfg();
    }

    // ---------- 热键捕获 ----------
    private void HkShow_Click(object sender, RoutedEventArgs e) => EnterCapture("show");
    private void HkRun_Click(object sender, RoutedEventArgs e) => EnterCapture("run");

    private void EnterCapture(string target)
    {
        _hotkey?.Clear();
        _capturing = true;
        _captureTarget = target;
        var btn = target == "show" ? HkShowBtn : HkRunBtn;
        btn.Background = (Brush)FindResource("AccentHover");
        btn.Foreground = Brushes.White;
        btn.Content = "按下组合键…  Esc 取消";
        PreviewKeyDown += CaptureKeyDown;
        Focus();
        Keyboard.Focus(this);
    }

    private void CaptureKeyDown(object sender, KeyEventArgs e)
    {
        if (!_capturing) return;
        if (e.Key == Key.Escape) { ExitCapture(cancel: true); e.Handled = true; return; }

        // 忽略纯修饰键
        if (e.Key is Key.LeftCtrl or Key.RightCtrl or Key.LeftAlt or Key.RightAlt
            or Key.LeftShift or Key.RightShift or Key.LWin or Key.RWin)
            return;

        var mods = Keyboard.Modifiers;
        uint m = 0;
        var parts = new System.Collections.Generic.List<string>();
        if (mods.HasFlag(ModifierKeys.Control)) { m |= NativeMethods.MOD_CONTROL; parts.Add("Ctrl"); }
        if (mods.HasFlag(ModifierKeys.Alt)) { m |= NativeMethods.MOD_ALT; parts.Add("Alt"); }
        if (mods.HasFlag(ModifierKeys.Shift)) { m |= NativeMethods.MOD_SHIFT; parts.Add("Shift"); }
        if (mods.HasFlag(ModifierKeys.Windows)) { m |= NativeMethods.MOD_WIN; parts.Add("Win"); }

        int vk = KeyInterop.VirtualKeyFromKey(e.Key);
        if (vk == 0 || (m & (NativeMethods.MOD_CONTROL | NativeMethods.MOD_ALT | NativeMethods.MOD_WIN)) == 0)
            return;

        parts.Add(LabelFromKey(e.Key));
        var label = string.Join(" + ", parts);
        e.Handled = true;
        ApplyHotkey(_captureTarget!, (uint)vk, m, label);
    }

    private void ApplyHotkey(string target, uint vk, uint mods, string label)
    {
        var def = new HotkeyDef { Mods = mods, Vk = vk, Label = label };
        int checkId;
        if (target == "show") { _cfg.Hotkeys.Show = def; checkId = HkIdShow; }
        else { _cfg.Hotkeys.Run = def; checkId = HkIdRun; }
        SaveCfg();
        ApplyHotkeys();
        ExitCapture(cancel: false);

        // 被占用提示
        if (_hotkey != null && !_hotkey.Ok.GetValueOrDefault(checkId))
        {
            var btn = target == "show" ? HkShowBtn : HkRunBtn;
            btn.Content = $"{label}（可能被占用）";
            btn.Foreground = (Brush)FindResource("Hint");
        }
    }

    private void ExitCapture(bool cancel)
    {
        _capturing = false;
        _captureTarget = null;
        PreviewKeyDown -= CaptureKeyDown;
        HkShowBtn.Background = (Brush)FindResource("ChipFg");
        HkShowBtn.Foreground = (Brush)FindResource("Text");
        HkRunBtn.Background = (Brush)FindResource("ChipFg");
        HkRunBtn.Foreground = (Brush)FindResource("Text");
        HkShowBtn.Content = _cfg.Hotkeys.Show.Label;
        HkRunBtn.Content = _cfg.Hotkeys.Run.Label;
        ApplyHotkeys();
    }

    private void ApplyHotkeys()
    {
        if (_hotkey == null) return;
        _hotkey.Set(new[]
        {
            (HkIdShow, _cfg.Hotkeys.Show.Mods, _cfg.Hotkeys.Show.Vk, (Action)ToggleVisibility),
            (HkIdRun, _cfg.Hotkeys.Run.Mods, _cfg.Hotkeys.Run.Vk, (Action)Toggle),
        });
    }

    // ---------- 恢复默认 ----------
    private void BtnReset_Click(object sender, RoutedEventArgs e) => ResetDefaults();

    private void ResetDefaults()
    {
        if (MessageBox.Show(this, "将清除全部配置（模式/间隔/热键/开关/历史）并恢复默认，确定？",
                "恢复默认", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;

        ConfigStore.Delete();
        Autostart.Set(false);
        if (_engine.IsRunning) _engine.Stop();

        _cfg = AppConfig.Default();
        _engine.Mode = _cfg.ModeEnum;
        _engine.Interval = _cfg.Interval;
        _engine.Jitter = _cfg.Jitter;
        ApplyUiFromConfig();
        UpdateRunUi();
        ApplyHotkeys();
        SaveCfg();
        try { _tray.ShowBalloon("防熄屏", "已恢复默认设置"); } catch { /* ignore */ }
    }

    // ---------- 显隐 ----------
    public void ToggleVisibility()
    {
        if (_visible) HideToTray();
        else Restore();
    }

    private void HideToTray()
    {
        Hide();
        _visible = false;
    }

    private void Restore()
    {
        Show();
        Topmost = true;
        _visible = true;
    }

    // ---------- 配置 / 退出 ----------
    private void SaveCfg() => ConfigStore.Save(_cfg);

    private void Quit()
    {
        if (_cleaned) return;
        _cleaned = true;
        if (_engine.SessionStart is DateTime s)
        {
            _cfg.LastSession = (DateTime.Now - s).TotalSeconds;
            SaveCfg();
        }
        _engine.Stop();
        try { _hotkey?.Dispose(); } catch { /* ignore */ }
        try { _tray.Dispose(); } catch { /* ignore */ }
        try { _appIcon.Dispose(); } catch { /* ignore */ }
        SaveCfg();
        Application.Current.Shutdown();
    }

    protected override void OnClosed(EventArgs e)
    {
        base.OnClosed(e);
        Quit();
    }

    // ---------- 工具 ----------
    private static string FmtDur(double seconds)
    {
        int s = (int)seconds;
        int h = s / 3600, m = (s % 3600) / 60, sec = s % 60;
        return h > 0 ? $"{h}:{m:D2}:{sec:D2}" : $"{m}:{sec:D2}";
    }

    private static string LabelFromKey(Key k)
    {
        string s = k.ToString();
        if (s.Length == 2 && s[0] == 'D' && char.IsDigit(s[1])) return s.Substring(1); // D0..D9
        if (s.Length == 1 && (char.IsLetterOrDigit(s[0]))) return s.ToUpper();
        return k switch
        {
            Key.Space => "Space",
            Key.Up => "↑",
            Key.Down => "↓",
            Key.Left => "←",
            Key.Right => "→",
            _ => s,
        };
    }
}
