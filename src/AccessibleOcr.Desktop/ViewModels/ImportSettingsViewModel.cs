using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class ImportSettingsViewModel : ObservableObject
{
    private string _selectedLanguage = "한국어";
    private bool _useAllPages = true;
    private string _startPage = "1";
    private string _endPage = "1";
    private string _processingPolicy = "조직 정책에 따라 처리";
    private bool _detectBody = true;
    private bool _detectTables = true;
    private bool _detectCharts = true;
    private bool _detectMath = true;
    private bool _detectMusic = true;
    private bool _detectImages = true;

    public string SelectedLanguage
    {
        get => _selectedLanguage;
        set => SetProperty(ref _selectedLanguage, value);
    }

    public bool UseAllPages
    {
        get => _useAllPages;
        set
        {
            if (SetProperty(ref _useAllPages, value))
            {
                NotifyPageRangeChanged();
            }
        }
    }

    public string StartPage
    {
        get => _startPage;
        set
        {
            if (SetProperty(ref _startPage, value))
            {
                NotifyPageRangeChanged();
            }
        }
    }

    public string EndPage
    {
        get => _endPage;
        set
        {
            if (SetProperty(ref _endPage, value))
            {
                NotifyPageRangeChanged();
            }
        }
    }

    public bool IsCustomPageRangeEnabled => !UseAllPages;
    public bool IsPageRangeValid => UseAllPages || TryGetCustomPageRange(out _, out _);
    public string PageRangeValidationMessage
    {
        get
        {
            if (UseAllPages)
            {
                return "PDF의 모든 페이지를 분석합니다.";
            }

            if (!int.TryParse(StartPage, out var start) || !int.TryParse(EndPage, out var end))
            {
                return "시작 페이지와 끝 페이지에 숫자만 입력하세요.";
            }

            if (start < 1 || end < 1)
            {
                return "페이지 번호는 1 이상이어야 합니다.";
            }

            return start <= end
                ? $"{start}페이지부터 {end}페이지까지 분석합니다."
                : "시작 페이지는 끝 페이지보다 클 수 없습니다.";
        }
    }

    public string ProcessingPolicy
    {
        get => _processingPolicy;
        set => SetProperty(ref _processingPolicy, value);
    }

    public bool DetectBody
    {
        get => _detectBody;
        set => SetProperty(ref _detectBody, value);
    }

    public bool DetectTables
    {
        get => _detectTables;
        set => SetProperty(ref _detectTables, value);
    }

    public bool DetectCharts
    {
        get => _detectCharts;
        set => SetProperty(ref _detectCharts, value);
    }

    public bool DetectMath
    {
        get => _detectMath;
        set => SetProperty(ref _detectMath, value);
    }

    public bool DetectMusic
    {
        get => _detectMusic;
        set => SetProperty(ref _detectMusic, value);
    }

    public bool DetectImages
    {
        get => _detectImages;
        set => SetProperty(ref _detectImages, value);
    }

    public ImportOptions ToOptions() => new()
    {
        Language = SelectedLanguage,
        PageRange = BuildPageRange(),
        ProcessingPolicy = ProcessingPolicy,
        DetectBody = DetectBody,
        DetectTables = DetectTables,
        DetectCharts = DetectCharts,
        DetectMath = DetectMath,
        DetectMusic = DetectMusic,
        DetectImages = DetectImages
    };

    private string BuildPageRange()
    {
        if (UseAllPages)
        {
            return "전체 페이지";
        }

        if (!TryGetCustomPageRange(out var start, out var end))
        {
            throw new InvalidOperationException(PageRangeValidationMessage);
        }

        return $"{start}-{end}";
    }

    private bool TryGetCustomPageRange(out int start, out int end)
    {
        start = 0;
        end = 0;
        return int.TryParse(StartPage, out start)
            && int.TryParse(EndPage, out end)
            && start >= 1
            && end >= 1
            && start <= end;
    }

    private void NotifyPageRangeChanged()
    {
        OnPropertyChanged(nameof(IsCustomPageRangeEnabled));
        OnPropertyChanged(nameof(IsPageRangeValid));
        OnPropertyChanged(nameof(PageRangeValidationMessage));
    }
}
