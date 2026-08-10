using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class AnalysisViewModel : ObservableObject
{
    private readonly Func<IProgress<ProcessingJob>, CancellationToken, Task> _runPipelineAsync;
    private int _progress;
    private string _statusText = "분석을 시작하면 OCR API Job 상태가 표시됩니다.";
    private bool _isRunning;
    private bool _isReady;
    private string _foundObjects = "결과 패키지(book.xml + review.json)를 기다리고 있습니다.";

    public AnalysisViewModel(Func<IProgress<ProcessingJob>, CancellationToken, Task> runPipelineAsync)
    {
        _runPipelineAsync = runPipelineAsync;
        StartCommand = new AsyncRelayCommand(_ => StartAsync(), _ => !IsRunning && !IsReady);
    }

    public int Progress
    {
        get => _progress;
        private set => SetProperty(ref _progress, value);
    }

    public string StatusText
    {
        get => _statusText;
        private set => SetProperty(ref _statusText, value);
    }

    public bool IsRunning
    {
        get => _isRunning;
        private set
        {
            if (SetProperty(ref _isRunning, value))
            {
                StartCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public bool IsReady
    {
        get => _isReady;
        private set
        {
            if (SetProperty(ref _isReady, value))
            {
                StartCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public string FoundObjects
    {
        get => _foundObjects;
        private set => SetProperty(ref _foundObjects, value);
    }

    public AsyncRelayCommand StartCommand { get; }

    public void Reset()
    {
        Progress = 0;
        StatusText = "분석 시작을 누르면 PDF를 OCR API에 업로드합니다.";
        FoundObjects = "결과 패키지(book.xml + review.json)를 기다리고 있습니다.";
        IsReady = false;
    }

    public void SetFoundObjects(IEnumerable<ReviewBlock> blocks)
    {
        var list = blocks.ToArray();
        FoundObjects = $"본문 {list.Count(block => block.Type == BlockType.Text)} · 표/도표 {list.Count(block => block.Type is BlockType.Table or BlockType.Graph)} · 수식 {list.Count(block => block.Type == BlockType.Math)} · 악보 {list.Count(block => block.Type == BlockType.Music)} · 검토 필요 {list.Count(block => block.ReviewStatus == ReviewStatus.NeedsReview)}";
    }

    private async Task StartAsync()
    {
        IsRunning = true;
        try
        {
            var progress = new Progress<ProcessingJob>(ReportJob);
            await _runPipelineAsync(progress, CancellationToken.None);
            Progress = 100;
            StatusText = "DTBook과 검수 사이드카를 가져왔습니다. 검수 작업공간을 열 수 있습니다.";
            IsReady = true;
        }
        catch (Exception exception)
        {
            StatusText = $"분석 실패: {exception.Message}";
            FoundObjects = "OCR API 주소, Job 응답, 결과 패키지 형식을 확인하세요.";
        }
        finally
        {
            IsRunning = false;
        }
    }

    private void ReportJob(ProcessingJob job)
    {
        Progress = job.Progress ?? job.Status.ToLowerInvariant() switch
        {
            "queued" => 5,
            "processing" => Math.Max(15, Progress),
            "done" => 95,
            _ => Progress
        };
        StatusText = job.Message ?? $"OCR Job {job.Id}: {job.Status}";
    }
}
