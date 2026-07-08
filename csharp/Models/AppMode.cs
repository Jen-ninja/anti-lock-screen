#nullable enable
namespace AntiLockScreen.Models;

/// <summary>防熄屏模式（与 Python 版 4 模式一致）。</summary>
public enum AppMode
{
    Keyboard,
    Mouse,
    Api,
    Hybrid,
}

public static class AppModes
{
    /// <summary>UI 显示的中文标签。</summary>
    public static string Label(AppMode m) => m switch
    {
        AppMode.Keyboard => "键盘",
        AppMode.Mouse => "鼠标",
        AppMode.Api => "API",
        AppMode.Hybrid => "键盘+API",
        _ => m.ToString(),
    };

    /// <summary>写配置用的小写字符串（与 Python config.json 互通）。</summary>
    public static string ToConfig(AppMode m) => m switch
    {
        AppMode.Keyboard => "keyboard",
        AppMode.Mouse => "mouse",
        AppMode.Api => "api",
        AppMode.Hybrid => "hybrid",
        _ => "keyboard",
    };

    public static AppMode FromConfig(string? s) => s switch
    {
        "keyboard" => AppMode.Keyboard,
        "mouse" => AppMode.Mouse,
        "api" => AppMode.Api,
        "hybrid" => AppMode.Hybrid,
        _ => AppMode.Keyboard,
    };
}
