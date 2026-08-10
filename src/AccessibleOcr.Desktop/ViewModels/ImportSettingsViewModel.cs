using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class ImportSettingsViewModel : ObservableObject
{
    private string _selectedLanguage = "한국어";
    private string _pageRange = "전체 페이지 (1-28)";
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

    public string PageRange
    {
        get => _pageRange;
        set => SetProperty(ref _pageRange, value);
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
        PageRange = PageRange,
        ProcessingPolicy = ProcessingPolicy,
        DetectBody = DetectBody,
        DetectTables = DetectTables,
        DetectCharts = DetectCharts,
        DetectMath = DetectMath,
        DetectMusic = DetectMusic,
        DetectImages = DetectImages
    };
}
