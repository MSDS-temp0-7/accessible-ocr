using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;
using AccessibleOcr.Desktop.Services;
using System.IO;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class MainViewModel : ObservableObject
{
    private readonly IDocumentService _documentService;
    private object _currentView;

    public MainViewModel(IDocumentService documentService, IFilePicker filePicker, AuthenticatedUser currentUser)
    {
        _documentService = documentService;
        CurrentUser = currentUser;
        Capabilities = UserCapabilities.For(currentUser.Role);
        Home = new HomeViewModel(filePicker, Capabilities.CanImport);
        ImportSettings = new ImportSettingsViewModel();
        TableDetail = new TableDetailViewModel();
        MathDetail = new MathDetailViewModel();
        MusicDetail = new MusicDetailViewModel();
        Export = new ExportViewModel(Capabilities.CanExport);
        ReviewWorkspace = new ReviewWorkspaceViewModel(documentService, NavigateTo, Capabilities.CanReview);
        Analysis = new AnalysisViewModel(RunPipelineAsync);

        _currentView = Home;
        NavigateCommand = new RelayCommand(Navigate, CanNavigate);
        StartAnalysisCommand = new RelayCommand(_ => StartAnalysis(), _ => Capabilities.CanImport);
    }

    public AuthenticatedUser CurrentUser { get; }
    public UserCapabilities Capabilities { get; }
    public bool CanImport => Capabilities.CanImport;
    public bool CanReview => Capabilities.CanReview;
    public bool CanExport => Capabilities.CanExport;

    public HomeViewModel Home { get; }
    public ImportSettingsViewModel ImportSettings { get; }
    public AnalysisViewModel Analysis { get; }
    public ReviewWorkspaceViewModel ReviewWorkspace { get; }
    public TableDetailViewModel TableDetail { get; }
    public MathDetailViewModel MathDetail { get; }
    public MusicDetailViewModel MusicDetail { get; }
    public ExportViewModel Export { get; }

    public object CurrentView
    {
        get => _currentView;
        private set => SetProperty(ref _currentView, value);
    }

    public RelayCommand NavigateCommand { get; }
    public RelayCommand StartAnalysisCommand { get; }

    private void Navigate(object? destination) => NavigateTo(destination?.ToString() ?? "Home");

    private bool CanNavigate(object? destination)
    {
        return destination?.ToString() switch
        {
            "ImportSettings" or "Analysis" => CanImport,
            "Review" or "TableDetail" or "MathDetail" or "MusicDetail" => CanReview,
            "Export" => CanExport,
            _ => true
        };
    }

    private void NavigateTo(string destination)
    {
        if (!CanNavigate(destination))
        {
            Home.FileStatus = "현재 계정에는 이 기능을 사용할 권한이 없습니다.";
            CurrentView = Home;
            return;
        }

        if (destination == "Review" && !ReviewWorkspace.HasDocument)
        {
            Home.FileStatus = "검수 작업공간은 실제 OCR 결과 패키지를 받은 뒤 열 수 있습니다.";
            CurrentView = Home;
            return;
        }

        var selectedBlock = ReviewWorkspace.SelectedBlock;
        if (destination == "TableDetail" && selectedBlock is not null)
        {
            TableDetail.Load(selectedBlock);
        }
        else if (destination == "MathDetail" && selectedBlock is not null)
        {
            MathDetail.Load(selectedBlock);
        }
        else if (destination == "MusicDetail" && selectedBlock is not null)
        {
            MusicDetail.Load(selectedBlock);
        }

        CurrentView = destination switch
        {
            "ImportSettings" => ImportSettings,
            "Analysis" => Analysis,
            "Review" => ReviewWorkspace,
            "TableDetail" => TableDetail,
            "MathDetail" => MathDetail,
            "MusicDetail" => MusicDetail,
            "Export" => Export,
            _ => Home
        };
    }

    private void StartAnalysis()
    {
        if (!Home.HasSelectedFile)
        {
            Home.FileStatus = "분석을 시작하려면 PDF 파일을 먼저 선택하세요.";
            CurrentView = Home;
            return;
        }

        Analysis.Reset();
        ReviewWorkspace.Reset();
        Export.Reset();
        CurrentView = Analysis;
    }

    private async Task RunPipelineAsync(IProgress<ProcessingJob> progress, CancellationToken cancellationToken)
    {
        var sourcePath = Home.SelectedFilePath ?? throw new InvalidOperationException("분석할 PDF가 선택되지 않았습니다.");
        var job = await _documentService.SubmitAsync(sourcePath, ImportSettings.ToOptions(), cancellationToken);
        progress.Report(job);

        while (!job.IsCompleted && !job.IsFailed)
        {
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
            job = await _documentService.GetJobAsync(job.Id, cancellationToken);
            progress.Report(job);
        }

        if (job.IsFailed)
        {
            throw new InvalidOperationException(job.Error ?? job.Message ?? "OCR 파이프라인이 실패했습니다.");
        }

        var result = await _documentService.GetResultAsync(job, Path.GetFileName(sourcePath), cancellationToken);
        await ReviewWorkspace.LoadAsync(result);
        Export.Load(result);
        Analysis.SetFoundObjects(result.Blocks);
    }
}
