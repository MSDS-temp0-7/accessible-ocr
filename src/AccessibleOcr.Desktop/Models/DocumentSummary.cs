namespace AccessibleOcr.Desktop.Models;

public sealed record DocumentSummary(
    string Id,
    string Title,
    DocumentStatus Status,
    DateTimeOffset CreatedAt);

