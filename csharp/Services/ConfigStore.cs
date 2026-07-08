#nullable enable
using System;
using System.IO;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using AntiLockScreen.Models;

namespace AntiLockScreen.Services;

/// <summary>
/// 配置持久化：读写 %APPDATA%\AntiLockScreen\config.json。
/// 路径与 schema 均与 Python 版一致，两版可互相读取对方配置。
/// </summary>
public static class ConfigStore
{
    private static readonly string Dir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "AntiLockScreen");

    private static readonly string FilePath = Path.Combine(Dir, "config.json");

    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        // 与 Python ensure_ascii=False 一致：中文直接写出，不转义成 \uXXXX
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static AppConfig Load()
    {
        AppConfig cfg;
        try
        {
            if (!File.Exists(FilePath)) return AppConfig.Default();
            var json = File.ReadAllText(FilePath);
            cfg = JsonSerializer.Deserialize<AppConfig>(json, Options) ?? AppConfig.Default();
        }
        catch
        {
            cfg = AppConfig.Default();
        }
        // 读到残缺配置（含 hotkeys 为 null）时补默认热键，避免热键不可用或 NRE
        var def = AppConfig.Default();
        if (cfg.Hotkeys is null) cfg.Hotkeys = def.Hotkeys;
        if (cfg.Hotkeys.Show is null || !cfg.Hotkeys.Show.IsValid) cfg.Hotkeys.Show = def.Hotkeys.Show;
        if (cfg.Hotkeys.Run is null || !cfg.Hotkeys.Run.IsValid) cfg.Hotkeys.Run = def.Hotkeys.Run;
        return cfg;
    }

    public static void Save(AppConfig cfg)
    {
        try
        {
            Directory.CreateDirectory(Dir);
            File.WriteAllText(FilePath, JsonSerializer.Serialize(cfg, Options));
        }
        catch
        {
            // 配置失败不应影响运行
        }
    }

    public static void Delete()
    {
        try { if (File.Exists(FilePath)) File.Delete(FilePath); }
        catch { /* ignore */ }
    }
}
