using System.Collections.ObjectModel;
using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;
using AccessibleOcr.Desktop.Services;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class ReviewWorkspaceViewModel : ObservableObject
{
    private readonly IDocumentService _documentService;
    private readonly Action<string> _openDetail;
    private string? _documentId;
    private bool _hasDocument;
    private string _documentTitle = "OCR 결과 패키지를 기다리고 있습니다.";
    private ReviewBlock? _selectedBlock;
    private int _selectedPageNumber = 1;
    private string _saveStatus = "DTBook 요소를 선택하면 검수 내용을 수정할 수 있습니다.";

    public ReviewWorkspaceViewModel(IDocumentService documentService, Action<string> openDetail)
    {
        _documentService = documentService;
        _openDetail = openDetail;
        MarkReviewedCommand = new AsyncRelayCommand(_ => MarkReviewedAsync(), _ => SelectedBlock is not null);
        SaveCommand = new AsyncRelayCommand(_ => SaveAsync(), _ => SelectedBlock is not null);
        OpenDetailCommand = new RelayCommand(_ => OpenDetail(), _ => SelectedBlock is not null && SelectedBlock.Type is BlockType.Table or BlockType.Graph or BlockType.Math or BlockType.Music);
    }

    public ObservableCollection<ReviewBlock> Blocks { get; } = [];
    public ObservableCollection<int> PageNumbers { get; } = [];

    public bool HasDocument
    {
        get => _hasDocument;
        private set => SetProperty(ref _hasDocument, value);
    }

    public string DocumentTitle
    {
        get => _documentTitle;
        private set => SetProperty(ref _documentTitle, value);
    }

    public ReviewBlock? SelectedBlock
    {
        get => _selectedBlock;
        set
        {
            if (SetProperty(ref _selectedBlock, value))
            {
                MarkReviewedCommand.RaiseCanExecuteChanged();
                SaveCommand.RaiseCanExecuteChanged();
                OpenDetailCommand.RaiseCanExecuteChanged();
                SaveStatus = value is null
                    ? "DTBook 요소를 선택하면 검수 내용을 수정할 수 있습니다."
                    : $"{value.Id} 요소를 편집 중입니다. 신뢰도 {value.Confidence:P0}, 페이지 {value.PageNumber}";
            }
        }
    }

    public int SelectedPageNumber
    {
        get => _selectedPageNumber;
        set
        {
            if (SetProperty(ref _selectedPageNumber, value))
            {
                SelectedBlock = Blocks.FirstOrDefault(block => block.PageNumber == value);
            }
        }
    }

    public string SaveStatus
    {
        get => _saveStatus;
        private set => SetProperty(ref _saveStatus, value);
    }

    public AsyncRelayCommand MarkReviewedCommand { get; }
    public AsyncRelayCommand SaveCommand { get; }
    public RelayCommand OpenDetailCommand { get; }

    public Task LoadAsync(OcrDocumentResult result)
    {
        _documentId = result.Document.Id;
        DocumentTitle = result.Document.Title;
        Blocks.Clear();
        PageNumbers.Clear();

        foreach (var page in result.Pages.OrderBy(page => page.PageIndex))
        {
            PageNumbers.Add(page.PageIndex + 1);
        }

        foreach (var block in result.Blocks)
        {
            Blocks.Add(block);
        }

        if (PageNumbers.Count == 0)
        {
            foreach (var pageNumber in Blocks.Select(block => block.PageNumber).Distinct().OrderBy(pageNumber => pageNumber))
            {
                PageNumbers.Add(pageNumber);
            }
        }

        if (PageNumbers.Count > 0)
        {
            SelectedPageNumber = PageNumbers.First();
        }

        HasDocument = true;

        return Task.CompletedTask;
    }

    public void Reset()
    {
        _documentId = null;
        Blocks.Clear();
        PageNumbers.Clear();
        SelectedBlock = null;
        SelectedPageNumber = 1;
        HasDocument = false;
    }

    private async Task MarkReviewedAsync()
    {
        if (SelectedBlock is null || _documentId is null)
        {
            return;
        }

        SelectedBlock.ReviewStatus = ReviewStatus.Reviewed;
        await _documentService.SaveReviewBlockAsync(_documentId, SelectedBlock);
        SaveStatus = $"{SelectedBlock.Id} 요소를 검토 완료로 저장했습니다.";
    }

    private async Task SaveAsync()
    {
        if (SelectedBlock is null || _documentId is null)
        {
            return;
        }

        await _documentService.SaveReviewBlockAsync(_documentId, SelectedBlock);
        SaveStatus = $"{SelectedBlock.Id} 수정 내용을 저장했습니다.";
    }

    private void OpenDetail()
    {
        if (SelectedBlock is null)
        {
            return;
        }

        var destination = SelectedBlock.Type switch
        {
            BlockType.Table or BlockType.Graph => "TableDetail",
            BlockType.Math => "MathDetail",
            BlockType.Music => "MusicDetail",
            _ => "Review"
        };
        _openDetail(destination);
    }
}
