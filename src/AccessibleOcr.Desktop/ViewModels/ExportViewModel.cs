using System.IO;
using System.Windows;
using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;
using AccessibleOcr.Desktop.Services;

namespace AccessibleOcr.Desktop.ViewModels;

/// <summary>
/// 실제 검수 결과를 DOCX/HWPX 또는 textNCX DAISY3 ZIP으로 로컬 저장한다.
/// DAISY3 저장 시 사용자용 HTML 검수 보고서를 같은 위치에 함께 생성한다.
/// </summary>
public sealed class ExportViewModel : ObservableObject
{
    private readonly bool _canExport;
    private readonly IFilePicker _filePicker;
    private readonly IDocumentExporter _documentExporter;
    private OcrDocumentResult? _result;
    private bool _hasDocument;
    private bool _isExporting;
    private string _documentTitle = string.Empty;
    private string _documentStructureStatus = string.Empty;
    private string _tableSummary = string.Empty;
    private string _tableStatus = string.Empty;
    private string _formulaSummary = string.Empty;
    private string _formulaStatus = string.Empty;
    private string _musicSummary = string.Empty;
    private string _musicStatus = string.Empty;
    private string _exportStatus = string.Empty;

    public ExportViewModel(
        bool canExport,
        IFilePicker filePicker,
        IDocumentExporter documentExporter)
    {
        _canExport = canExport;
        _filePicker = filePicker;
        _documentExporter = documentExporter;
        ExportDocxCommand = new AsyncRelayCommand(_ => ExportDocxAsync(), _ => CanExport());
        ExportHwpxCommand = new AsyncRelayCommand(_ => ExportHwpxAsync(), _ => CanExport());
        ExportCommand = new AsyncRelayCommand(_ => ExportDaisyAsync(), _ => CanExport());
    }

    public AsyncRelayCommand ExportDocxCommand { get; }
    public AsyncRelayCommand ExportHwpxCommand { get; }
    public AsyncRelayCommand ExportCommand { get; }

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
            RaiseExportCommandState();
        }
    }

    public bool IsExporting
    {
        get => _isExporting;
        private set
        {
            if (SetProperty(ref _isExporting, value))
            {
                RaiseExportCommandState();
            }
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
        _result = result;
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
            ? "검수가 완료되었습니다. DAISY3, Word와 한글 파일을 로컬로 저장할 수 있습니다."
            : $"검수가 필요한 항목 {needsReview}건이 있습니다. 내보낸 파일과 검수 보고서에 해당 상태가 함께 기록됩니다.";
        HasDocument = true;
    }

    public void Reset()
    {
        _result = null;
        IsExporting = false;
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

    private async Task ExportDocxAsync()
    {
        if (_result is null)
        {
            return;
        }

        var path = await _filePicker.PickSaveFileAsync(
            "검수 결과를 Word 문서로 저장",
            $"{SuggestedBaseName()}.docx",
            "Word 문서 (*.docx)|*.docx",
            ".docx");
        if (path is null)
        {
            return;
        }

        await RunExportAsync(
            () => _documentExporter.ExportDocxAsync(_result, path),
            $"Word 문서를 저장했습니다: {path}");
    }

    private async Task ExportHwpxAsync()
    {
        if (_result is null)
        {
            return;
        }

        var path = await _filePicker.PickSaveFileAsync(
            "검수 결과를 한글 문서로 저장",
            $"{SuggestedBaseName()}.hwpx",
            "한글 표준 문서 (*.hwpx)|*.hwpx",
            ".hwpx");
        if (path is null)
        {
            return;
        }

        await RunExportAsync(
            () => _documentExporter.ExportHwpxAsync(_result, path),
            $"한글 문서를 저장했습니다: {path}");
    }

    private async Task RunExportAsync(Func<Task> export, string successMessage)
    {
        IsExporting = true;
        ExportStatus = "파일을 생성하는 중입니다.";
        try
        {
            await export();
            ExportStatus = successMessage;
        }
        catch (UnauthorizedAccessException)
        {
            ExportStatus = "선택한 위치에 파일을 저장할 권한이 없습니다. 다른 폴더를 선택하세요.";
        }
        catch (IOException exception)
        {
            ExportStatus = $"파일을 저장하지 못했습니다. 파일이 열려 있는지 확인하세요. ({exception.Message})";
        }
        catch (InvalidOperationException exception)
        {
            ExportStatus = exception.Message;
        }
        catch (Exception exception)
        {
            ExportStatus = $"내보내기 중 예상하지 못한 오류가 발생했습니다. ({exception.Message})";
        }
        finally
        {
            IsExporting = false;
        }
    }

    private async Task ExportDaisyAsync()
    {
        if (_result is null)
        {
            return;
        }

        var path = await _filePicker.PickSaveFileAsync(
            "검수 결과를 DAISY3 패키지로 저장",
            $"{SuggestedBaseName()}-DAISY3.zip",
            "DAISY3 패키지 (*.zip)|*.zip",
            ".zip");
        if (path is null)
        {
            return;
        }

        IsExporting = true;
        ExportStatus = "DAISY3 본문·탐색·패키지와 검수 보고서를 생성하는 중입니다.";
        try
        {
            var outcome = await _documentExporter.ExportDaisy3Async(_result, path);
            ExportStatus =
                $"DAISY3 패키지를 저장했습니다: {outcome.PackagePath}\n" +
                $"검수 보고서: {outcome.ReviewReportPath}\n" +
                $"기본 구조 검사 {outcome.ValidationMessages.Count}개 항목 통과";
        }
        catch (UnauthorizedAccessException)
        {
            ExportStatus = "선택한 위치에 파일을 저장할 권한이 없습니다. 다른 폴더를 선택하세요.";
        }
        catch (IOException exception)
        {
            ExportStatus = $"DAISY3 파일을 저장하지 못했습니다. 파일이 열려 있는지 확인하세요. ({exception.Message})";
        }
        catch (InvalidOperationException exception)
        {
            ExportStatus = exception.Message;
        }
        catch (Exception exception)
        {
            ExportStatus = $"DAISY3 내보내기 중 오류가 발생했습니다. ({exception.Message})";
        }
        finally
        {
            IsExporting = false;
        }
    }

    private bool CanExport() => _canExport && HasDocument && _result is not null && !IsExporting;

    private string SuggestedBaseName()
    {
        var name = Path.GetFileNameWithoutExtension(DocumentTitle);
        foreach (var invalidCharacter in Path.GetInvalidFileNameChars())
        {
            name = name.Replace(invalidCharacter, '_');
        }

        return string.IsNullOrWhiteSpace(name) ? "검수문서" : name.Trim();
    }

    private void RaiseExportCommandState()
    {
        ExportDocxCommand.RaiseCanExecuteChanged();
        ExportHwpxCommand.RaiseCanExecuteChanged();
        ExportCommand.RaiseCanExecuteChanged();
    }
}
