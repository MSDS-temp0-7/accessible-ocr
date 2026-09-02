namespace AccessibleOcr.Desktop.Models;

public sealed record OcrDocumentResult(
    DocumentSummary Document,
    IReadOnlyList<OcrPage> Pages,
    IReadOnlyList<ReviewBlock> Blocks);

public sealed record OcrPage(int PageIndex, int Width, int Height, int Dpi, byte[]? ImageBytes = null);
