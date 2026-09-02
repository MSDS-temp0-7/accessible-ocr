using System.Collections.ObjectModel;
using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;
using AccessibleOcr.Desktop.Services;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class ReviewWorkspaceViewModel : ObservableObject
{
    private readonly IDocumentService _documentService;
    private readonly Action<string> _openDetail;
    private readonly bool _canReview;
    private string? _documentId;
    private bool _hasDocument;
    private string _documentTitle = "OCR 결과 패키지를 기다리고 있습니다.";
    private ReviewBlock? _selectedBlock;
    private ReviewPageViewModel? _currentPage;
    private int _selectedPageNumber = 1;
    private string _saveStatus = "DTBook 요소를 선택하면 검수 내용을 수정할 수 있습니다.";
    private bool _changingPageFromBlock;

    public ReviewWorkspaceViewModel(IDocumentService documentService, Action<string> openDetail, bool canReview)
    {
        _documentService = documentService;
        _openDetail = openDetail;
        _canReview = canReview;
        MarkReviewedCommand = new AsyncRelayCommand(_ => MarkReviewedAsync(), _ => _canReview && SelectedBlock is not null);
        SaveCommand = new AsyncRelayCommand(_ => SaveAsync(), _ => _canReview && SelectedBlock is not null);
        OpenDetailCommand = new RelayCommand(_ => OpenDetail(), _ => _canReview && SelectedBlock is not null && SelectedBlock.Type is BlockType.Table or BlockType.Graph or BlockType.Math or BlockType.Music);
        SelectBlockCommand = new RelayCommand(block => SelectedBlock = block as ReviewBlock, block => block is ReviewBlock);
    }

    public ObservableCollection<ReviewBlock> Blocks { get; } = [];
    public ObservableCollection<ReviewBlock> PageBlocks { get; } = [];
    public ObservableCollection<int> PageNumbers { get; } = [];
    public ObservableCollection<ReviewPageViewModel> Pages { get; } = [];

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
                if (value is not null && value.PageNumber != SelectedPageNumber)
                {
                    _changingPageFromBlock = true;
                    SelectedPageNumber = value.PageNumber;
                    _changingPageFromBlock = false;
                }

                foreach (var block in Blocks)
                {
                    block.IsSelectedForOverlay = ReferenceEquals(block, value);
                }

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
                CurrentPage = Pages.FirstOrDefault(page => page.PageNumber == value);
                RefreshPageBlocks();
                if (!_changingPageFromBlock)
                {
                    SelectedBlock = PageBlocks.FirstOrDefault();
                }
            }
        }
    }

    public ReviewPageViewModel? CurrentPage
    {
        get => _currentPage;
        private set
        {
            if (SetProperty(ref _currentPage, value))
            {
                OnPropertyChanged(nameof(HasPageImage));
                OnPropertyChanged(nameof(PageImageStatus));
            }
        }
    }

    public bool HasPageImage => CurrentPage?.HasImage == true;
    public string PageImageStatus => HasPageImage
        ? $"{SelectedPageNumber}페이지 원본과 {PageBlocks.Count}개 검출 영역을 표시합니다."
        : "이 결과 패키지에는 원본 페이지 이미지가 없습니다. 새로 분석하면 미리보기가 포함됩니다.";
    public string PageObjectSummary => $"{SelectedPageNumber}페이지 객체 {PageBlocks.Count}개";

    public string SaveStatus
    {
        get => _saveStatus;
        private set => SetProperty(ref _saveStatus, value);
    }

    public AsyncRelayCommand MarkReviewedCommand { get; }
    public AsyncRelayCommand SaveCommand { get; }
    public RelayCommand OpenDetailCommand { get; }
    public RelayCommand SelectBlockCommand { get; }

    public Task LoadAsync(OcrDocumentResult result)
    {
        _documentId = result.Document.Id;
        DocumentTitle = result.Document.Title;
        Blocks.Clear();
        PageBlocks.Clear();
        PageNumbers.Clear();
        Pages.Clear();
        SelectedBlock = null;
        CurrentPage = null;
        _selectedPageNumber = 0;
        OnPropertyChanged(nameof(SelectedPageNumber));

        foreach (var page in result.Pages.OrderBy(page => page.PageIndex))
        {
            PageNumbers.Add(page.PageIndex + 1);
            Pages.Add(new ReviewPageViewModel(page));
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
        PageBlocks.Clear();
        PageNumbers.Clear();
        Pages.Clear();
        SelectedBlock = null;
        CurrentPage = null;
        SelectedPageNumber = 1;
        HasDocument = false;
    }

    private void RefreshPageBlocks()
    {
        PageBlocks.Clear();
        foreach (var block in Blocks.Where(block => block.PageNumber == SelectedPageNumber))
        {
            PageBlocks.Add(block);
        }

        OnPropertyChanged(nameof(PageObjectSummary));
        OnPropertyChanged(nameof(PageImageStatus));
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
