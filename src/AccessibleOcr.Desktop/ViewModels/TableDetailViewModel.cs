using System.Collections.ObjectModel;
using AccessibleOcr.Desktop.Infrastructure;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class TableDetailViewModel : ObservableObject
{
    private string _selectedMode = "개요 읽기";
    private string _currentLocation = "C2 · 청소년 · 2023 · 51%";

    public TableDetailViewModel()
    {
        Modes = ["개요 읽기", "셀 탐색", "선형 읽기"];
        Rows =
        [
            new TableRow("청소년", "42%", "51%", "58%"),
            new TableRow("성인", "36%", "43%", "49%"),
            new TableRow("고령자", "18%", "24%", "31%"),
            new TableRow("전체", "34%", "42%", "47%")
        ];
    }

    public ObservableCollection<string> Modes { get; }
    public ObservableCollection<TableRow> Rows { get; }

    public string SelectedMode
    {
        get => _selectedMode;
        set => SetProperty(ref _selectedMode, value);
    }

    public string CurrentLocation
    {
        get => _currentLocation;
        set => SetProperty(ref _currentLocation, value);
    }
}

public sealed record TableRow(string Category, string Year2022, string Year2023, string Year2024);

