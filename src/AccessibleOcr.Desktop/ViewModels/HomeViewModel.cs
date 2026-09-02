using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Services;
using System.IO;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class HomeViewModel : ObservableObject
{
    private readonly IFilePicker _filePicker;
    private readonly bool _canImport;
    private string _projectTitle = "새 OCR 프로젝트";
    private string _selectedFileName = "선택된 파일이 없습니다.";
    private string? _selectedFilePath;
    private string _readingMode = "정밀 변환";
    private string _fileStatus = "멀티페이지 PDF를 선택하면 OCR API에 업로드합니다.";
    private bool _analysisRunning;

    public HomeViewModel(IFilePicker filePicker, bool canImport)
    {
        _filePicker = filePicker;
        _canImport = canImport;
        SelectFileCommand = new AsyncRelayCommand(_ => SelectFileAsync(), _ => CanSelectFile);
    }

    public string ProjectTitle
    {
        get => _projectTitle;
        set => SetProperty(ref _projectTitle, value);
    }

    public string SelectedFileName
    {
        get => _selectedFileName;
        private set => SetProperty(ref _selectedFileName, value);
    }

    public string? SelectedFilePath
    {
        get => _selectedFilePath;
        private set
        {
            if (SetProperty(ref _selectedFilePath, value))
            {
                OnPropertyChanged(nameof(HasSelectedFile));
            }
        }
    }

    public bool HasSelectedFile => !string.IsNullOrWhiteSpace(SelectedFilePath);
    public bool CanImport => _canImport;
    public bool CanSelectFile => _canImport && !_analysisRunning;

    public string ReadingMode
    {
        get => _readingMode;
        set => SetProperty(ref _readingMode, value);
    }

    public string FileStatus
    {
        get => _fileStatus;
        set => SetProperty(ref _fileStatus, value);
    }

    public AsyncRelayCommand SelectFileCommand { get; }

    public void SetAnalysisRunning(bool isRunning)
    {
        if (_analysisRunning == isRunning)
        {
            return;
        }

        _analysisRunning = isRunning;
        OnPropertyChanged(nameof(CanSelectFile));
        SelectFileCommand.RaiseCanExecuteChanged();
        FileStatus = isRunning
            ? "OCR 분석이 진행 중입니다. 진행 중 작업 메뉴에서 상태를 확인할 수 있습니다."
            : HasSelectedFile
                ? "PDF가 선택되어 있습니다. 새 분석을 시작하거나 기존 결과를 확인할 수 있습니다."
                : "멀티페이지 PDF를 선택하면 OCR API에 업로드합니다.";
    }

    private async Task SelectFileAsync()
    {
        var selectedPath = await _filePicker.PickPdfAsync();
        if (string.IsNullOrWhiteSpace(selectedPath))
        {
            FileStatus = "파일 선택이 취소되었습니다.";
            return;
        }

        SelectedFilePath = selectedPath;
        SelectedFileName = Path.GetFileName(selectedPath);
        FileStatus = "PDF가 선택되었습니다. 가져오기 설정에서 분석 범위를 지정하세요.";
    }
}
