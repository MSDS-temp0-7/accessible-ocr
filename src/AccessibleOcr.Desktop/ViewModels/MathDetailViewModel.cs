using System.Collections.ObjectModel;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class MathDetailViewModel
{
    public MathDetailViewModel()
    {
        Symbols = ["F\n힘", "=\n같다", "m\n질량", "×\n곱하기", "a\n가속도"];
    }

    public ObservableCollection<string> Symbols { get; }
}

