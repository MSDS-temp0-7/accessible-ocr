using System.Collections.ObjectModel;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class MusicDetailViewModel
{
    public MusicDetailViewModel()
    {
        Measures = ["1마디\n도 미 솔", "2마디\n레 파 라", "3마디\n미 솔 도", "4마디\n파 라 도", "5마디\n솔 시 레", "6마디\n라 도 미", "7마디\n시 레 파", "8마디\n도 — —"];
    }

    public ObservableCollection<string> Measures { get; }
}

