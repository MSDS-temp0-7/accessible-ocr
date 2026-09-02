using AccessibleOcr.Desktop.Infrastructure;

namespace AccessibleOcr.Desktop.Models;

public sealed class ReviewBlock : ObservableObject
{
    private const double PreviewMaxWidth = 760;
    private string _content = string.Empty;
    private ReviewStatus _reviewStatus;
    private bool _isSelectedForOverlay;

    public required string Id { get; init; }
    public required int PageNumber { get; init; }
    public required int PageWidth { get; init; }
    public required int PageHeight { get; init; }
    public required BlockType Type { get; init; }
    public required double Confidence { get; init; }
    public required double X { get; init; }
    public required double Y { get; init; }
    public required double Width { get; init; }
    public required double Height { get; init; }
    public string? Revision { get; init; }
    public string? RegionReference { get; init; }

    public double NormalizedX => PageWidth == 0 ? 0 : X / PageWidth;
    public double NormalizedY => PageHeight == 0 ? 0 : Y / PageHeight;
    public double NormalizedWidth => PageWidth == 0 ? 0 : Width / PageWidth;
    public double NormalizedHeight => PageHeight == 0 ? 0 : Height / PageHeight;
    public double PreviewScale => PageWidth <= 0 ? 1 : Math.Min(1, PreviewMaxWidth / PageWidth);
    public double OverlayX => X * PreviewScale;
    public double OverlayY => Y * PreviewScale;
    public double OverlayWidth => Math.Max(4, Width * PreviewScale);
    public double OverlayHeight => Math.Max(4, Height * PreviewScale);
    public string TypeDisplayName => Type switch
    {
        BlockType.Table => "표",
        BlockType.Graph => "그림·그래프",
        BlockType.Math => "수식",
        BlockType.Music => "악보",
        BlockType.Image => "이미지",
        _ => "글"
    };
    public string AccessibleName => $"{PageNumber}페이지 {TypeDisplayName}, {Content}";

    public string Content
    {
        get => _content;
        set => SetProperty(ref _content, value);
    }

    public ReviewStatus ReviewStatus
    {
        get => _reviewStatus;
        set => SetProperty(ref _reviewStatus, value);
    }

    public bool IsSelectedForOverlay
    {
        get => _isSelectedForOverlay;
        set => SetProperty(ref _isSelectedForOverlay, value);
    }
}
