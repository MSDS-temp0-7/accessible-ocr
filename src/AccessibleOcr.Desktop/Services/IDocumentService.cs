using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

public interface IDocumentService
{
    Task<ProcessingJob> SubmitAsync(string filePath, ImportOptions options, CancellationToken cancellationToken = default);
    Task<ProcessingJob> GetJobAsync(string jobId, CancellationToken cancellationToken = default);
    Task<OcrDocumentResult> GetResultAsync(ProcessingJob job, string sourceFileName, CancellationToken cancellationToken = default);
    Task SaveReviewBlockAsync(string documentId, ReviewBlock block, CancellationToken cancellationToken = default);
}
