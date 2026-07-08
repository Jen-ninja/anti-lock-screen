#nullable enable
using System.Text.Json.Serialization;

namespace AntiLockScreen.Models;

/// <summary>
/// 配置模型 —— 字段名与 Python 版 config.json 完全一致（JsonPropertyName 显式指定），
/// 因此 C# 版与 Python 版读写同一份 %APPDATA%\AntiLockScreen\config.json，可无缝切换。
/// </summary>
public class AppConfig
{
    [JsonPropertyName("mode")] public string Mode { get; set; } = "keyboard";
    [JsonPropertyName("interval")] public int Interval { get; set; } = 60;
    [JsonPropertyName("autoon")] public bool AutoOn { get; set; } = true;
    [JsonPropertyName("jitter")] public bool Jitter { get; set; } = true;
    [JsonPropertyName("notify")] public bool Notify { get; set; } = true;
    [JsonPropertyName("last_session")] public double? LastSession { get; set; }
    [JsonPropertyName("hotkeys")] public HotkeyPair Hotkeys { get; set; } = new();

    public AppMode ModeEnum => AppModes.FromConfig(Mode);

    /// <summary>默认配置：键盘模式 / 60s / 全开 / Ctrl+Alt+S（显隐）/ Ctrl+Alt+D（开关）。</summary>
    public static AppConfig Default() => new()
    {
        Mode = "keyboard",
        Interval = 60,
        AutoOn = true,
        Jitter = true,
        Notify = true,
        LastSession = null,
        Hotkeys = new HotkeyPair
        {
            // MOD_CONTROL(2) | MOD_ALT(1) = 3
            Show = new HotkeyDef { Mods = 3, Vk = 0x53, Label = "Ctrl + Alt + S" },
            Run = new HotkeyDef { Mods = 3, Vk = 0x44, Label = "Ctrl + Alt + D" },
        },
    };

    /// <summary>返回一份当前状态的拷贝（不可变更新用）。</summary>
    public AppConfig Clone() => new()
    {
        Mode = Mode,
        Interval = Interval,
        AutoOn = AutoOn,
        Jitter = Jitter,
        Notify = Notify,
        LastSession = LastSession,
        Hotkeys = new HotkeyPair
        {
            Show = Hotkeys.Show.Clone(),
            Run = Hotkeys.Run.Clone(),
        },
    };
}

public class HotkeyPair
{
    [JsonPropertyName("show")] public HotkeyDef Show { get; set; } = new();
    [JsonPropertyName("run")] public HotkeyDef Run { get; set; } = new();
}

public class HotkeyDef
{
    [JsonPropertyName("mods")] public uint Mods { get; set; }
    [JsonPropertyName("vk")] public uint Vk { get; set; }
    [JsonPropertyName("label")] public string Label { get; set; } = "";

    public bool IsValid => Mods != 0 && Vk != 0 && !string.IsNullOrEmpty(Label);

    public HotkeyDef Clone() => new() { Mods = Mods, Vk = Vk, Label = Label };
}
