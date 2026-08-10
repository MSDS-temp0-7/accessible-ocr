using AccessibleOcr.Desktop.Infrastructure;

namespace AccessibleOcr.Desktop.Models;

public sealed class ReviewBlock : ObservableObject
{
    private string _content = string.Empty;
    private ReviewStatus _reviewStatus;

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
}
