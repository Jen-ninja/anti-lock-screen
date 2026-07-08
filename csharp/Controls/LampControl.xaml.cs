#nullable enable
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace AntiLockScreen.Controls;

/// <summary>
/// mini 台灯：IsOn 切换亮/灭两套配色 + 光束显隐（对应 Python make_lamp）。
/// </summary>
public partial class LampControl : UserControl
{
    public static readonly DependencyProperty IsOnProperty = DependencyProperty.Register(
        nameof(IsOn), typeof(bool), typeof(LampControl),
        new PropertyMetadata(false, (d, _) => ((LampControl)d).Apply()));

    public bool IsOn
    {
        get => (bool)GetValue(IsOnProperty);
        set => SetValue(IsOnProperty, value);
    }

    public LampControl()
    {
        InitializeComponent();
        Apply();
    }

    private void Apply()
    {
        bool on = IsOn;
        Shade.Fill = B(on ? "#E4B248" : "#787C84");
        ShadeHi.Fill = B(on ? "#FCDA80" : "#AAAEB6");
        Rim.Fill = B(on ? "#966C24" : "#464950");
        Bulb.Fill = B(on ? "#FFF7CD" : "#62656C");
        Joint.Fill = B(on ? "#966C24" : "#4A4D54");
        Pole.Fill = B(on ? "#E0DBCC" : "#9699A0");
        PoleHi.Fill = B(on ? "#F6F3EA" : "#B4B7BE");
        Base.Fill = B(on ? "#CCC6B6" : "#84878E");
        BaseTop.Fill = B(on ? "#E4DFD0" : "#9EA1A8");
        BaseShadow.Fill = B(on ? "#8A8576" : "#54575E");

        var beam = on ? Visibility.Visible : Visibility.Collapsed;
        Beam1.Visibility = beam;
        Beam2.Visibility = beam;
        Beam3.Visibility = beam;
        Beam1.Fill = B("#FFC054");
        Beam2.Fill = B("#FFD680");
        Beam3.Fill = B("#FFEEBC");
    }

    private static readonly Dictionary<string, SolidColorBrush> _cache = new();
    private static SolidColorBrush B(string hex)
    {
        if (_cache.TryGetValue(hex, out var b)) return b;
        var brush = new SolidColorBrush((Color)ColorConverter.ConvertFromString(hex));
        brush.Freeze();
        _cache[hex] = brush;
        return brush;
    }
}
