#nullable enable
using System;
using System.Diagnostics;
using System.IO;

namespace AntiLockScreen.Services;

/// <summary>
/// 开机自启：在 Startup 目录创建/删除「防熄屏.lnk」。
/// 沿用 Python 版的 PowerShell + WScript.Shell COM 方式，行为一致。
/// </summary>
public static class Autostart
{
    public static string LnkPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.Startup), "防熄屏.lnk");

    public static bool IsEnabled() => File.Exists(LnkPath);

    public static void Set(bool on)
    {
        if (on) CreateLnk();
        else DeleteLnk();
    }

    private static void DeleteLnk()
    {
        try { if (File.Exists(LnkPath)) File.Delete(LnkPath); }
        catch (Exception) { /* ignore */ }
    }

    private static void CreateLnk()
    {
        var exePath = Environment.ProcessPath;
        if (string.IsNullOrEmpty(exePath) || !File.Exists(exePath)) return;
        var workdir = Path.GetDirectoryName(exePath) ?? "";

        var ps =
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + Q(LnkPath) + ");" +
            "$s.TargetPath=" + Q(exePath) + ";" +
            "$s.Arguments='';" +
            "$s.WorkingDirectory=" + Q(workdir) + ";" +
            "$s.WindowStyle=7;" +
            "$s.Description='防熄屏';" +
            "$s.Save()";

        try
        {
            var psi = new ProcessStartInfo("powershell", "-NoProfile -Command " + ps)
            {
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                UseShellExecute = false,
            };
            Process.Start(psi)?.WaitForExit(5000);
        }
        catch (Exception) { /* ignore */ }
    }

    /// <summary>PowerShell 单引号转义：内部 ' → ''</summary>
    private static string Q(string s) => "'" + (s ?? "").Replace("'", "''") + "'";
}
