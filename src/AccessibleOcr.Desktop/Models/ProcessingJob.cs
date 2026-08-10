namespace AccessibleOcr.Desktop.Models;

public sealed record ProcessingJob(
    string Id,
    string Status,
    int? Progress,
    string? Message,
    string? DocumentId = null,
    string? Error = null)
{
    public bool IsCompleted => string.Equals(Status, "done", StringComparison.OrdinalIgnoreCase);
    public bool IsFailed => string.Equals(Status, "failed", StringComparison.OrdinalIgnoreCase);
}

