using System.Windows;
using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

/// <summary>
/// 검수 결과가 실제로 로드된 경우에만 내보내기 요약을 표시한다.
/// 내보내기 파일 생성 API는 모델 측 계약이 확정되면 연결한다.
/// </summary>
public sealed class ExportViewModel : ObservableObject
{
    private bool _hasDocument;
    private string _documentTitle = string.Empty;
    private string _documentStructureStatus = string.Empty;
    private string _tableSummary = string.Empty;
    private string _tableStatus = string.Empty;
    private string _formulaSummary = string.Empty;
    private string _formulaStatus = string.Empty;
    private string _musicSummary = string.Empty;
    private string _musicStatus = string.Empty;
    private string _exportStatus = string.Empty;

    public ExportViewModel()
    {
        ExportCommand = new RelayCommand(_ => Export());
    }

    public RelayCommand ExportCommand { get; }

    public bool HasDocument
    {
        get => _hasDocument;
        private set
        {
            if (!SetProperty(ref _hasDocument, value))
            {
                return;
            }

            OnPropertyChanged(nameof(ContentVisibility));
            OnPropertyChanged(nameof(EmptyStateVisibility));
        }
    }

    public string DocumentTitle
    {
        get => _documentTitle;
        private set => SetProperty(ref _documentTitle, value);
    }

    public string DocumentStructureStatus
    {
        get => _documentStructureStatus;
        private set => SetProperty(ref _documentStructureStatus, value);
    }

    public string TableSummary
    {
        get => _tableSummary;
        private set => SetProperty(ref _tableSummary, value);
    }

    public string TableStatus
    {
        get => _tableStatus;
        private set => SetProperty(ref _tableStatus, value);
    }

    public string FormulaSummary
    {
        get => _formulaSummary;
        private set => SetProperty(ref _formulaSummary, value);
    }

    public string FormulaStatus
    {
        get => _formulaStatus;
        private set => SetProperty(ref _formulaStatus, value);
    }

    public string MusicSummary
    {
        get => _musicSummary;
        private set => SetProperty(ref _musicSummary, value);
    }

    public string MusicStatus
    {
        get => _musicStatus;
        private set => SetProperty(ref _musicStatus, value);
    }

    public string ExportStatus
    {
        get => _exportStatus;
        private set => SetProperty(ref _exportStatus, value);
    }

    public Visibility ContentVisibility => HasDocument ? Visibility.Visible : Visibility.Collapsed;
    public Visibility EmptyStateVisibility => HasDocument ? Visibility.Collapsed : Visibility.Visible;

    public void Load(OcrDocumentResult result)
    {
        var blocks = result.Blocks;
        var needsReview = blocks.Count(block => block.ReviewStatus != ReviewStatus.Reviewed);
        var tables = blocks.Count(block => block.Type is BlockType.Table or BlockType.Graph);
        var formulas = blocks.Count(block => block.Type == BlockType.Math);
        var music = blocks.Count(block => block.Type == BlockType.Music);

        DocumentTitle = result.Document.Title;
        DocumentStructureStatus = needsReview == 0 ? "검수 완료" : $"{needsReview}건 확인";
        TableSummary = $"표·도표 {tables}";
        TableStatus = tables == 0 ? "해당 없음" : "검수 대상";
        FormulaSummary = $"수식 {formulas}";
        FormulaStatus = formulas == 0 ? "해당 없음" : "검수 대상";
        MusicSummary = $"악보 {music}";
        MusicStatus = music == 0 ? "해당 없음" : "검수 대상";
        ExportStatus = needsReview == 0
            ? "실제 OCR 결과를 기준으로 검수 완료되었습니다."
            : $"검수가 필요한 항목 {needsReview}건이 있습니다. 내보내기 시 검수 보고서에 기록됩니다.";
        HasDocument = true;
    }

    public void Reset()
    {
        HasDocument = false;
        DocumentTitle = string.Empty;
        DocumentStructureStatus = string.Empty;
        TableSummary = string.Empty;
        TableStatus = string.Empty;
        FormulaSummary = string.Empty;
        FormulaStatus = string.Empty;
        MusicSummary = string.Empty;
        MusicStatus = string.Empty;
        ExportStatus = string.Empty;
    }

    private void Export()
    {
        if (!HasDocument)
        {
            return;
        }

        ExportStatus = "내보내기 API 계약이 확정되면 실제 DAISY/Word 파일 생성 기능을 연결합니다.";
    }
}
