using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

public interface IDocumentExporter
{
    Task ExportDocxAsync(
        OcrDocumentResult result,
        string destinationPath,
        CancellationToken cancellationToken = default);

    Task ExportHwpxAsync(
        OcrDocumentResult result,
        string destinationPath,
        CancellationToken cancellationToken = default);

    Task<DaisyExportOutcome> ExportDaisy3Async(
        OcrDocumentResult result,
        string destinationPath,
        CancellationToken cancellationToken = default);
}

public sealed record DaisyExportOutcome(
    string PackagePath,
    string ReviewReportPath,
    IReadOnlyList<string> ValidationMessages);
