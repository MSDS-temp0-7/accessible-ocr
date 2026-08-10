using System.Text.Json;
using System.IO;

namespace AccessibleOcr.Desktop.Services;

public sealed class OcrApiOptions
{
    public string BaseUrl { get; init; } = "http://localhost:8000";
    public string JobsPath { get; init; } = "/api/v1/jobs";
    public string ReviewPathTemplate { get; init; } = "/api/v1/documents/{documentId}/elements/{elementId}/review";

    public static OcrApiOptions Load()
    {
        var basePath = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
        var localPath = Path.Combine(AppContext.BaseDirectory, "appsettings.Local.json");
        var values = new OcrApiOptions();

        if (File.Exists(basePath))
        {
            values = Read(basePath, values);
        }

        if (File.Exists(localPath))
        {
            values = Read(localPath, values);
        }

        return values;
    }

    private static OcrApiOptions Read(string path, OcrApiOptions fallback)
    {
        using var json = JsonDocument.Parse(File.ReadAllText(path));
        if (!json.RootElement.TryGetProperty("OcrApi", out var api))
        {
            return fallback;
        }

        return new OcrApiOptions
        {
            BaseUrl = api.TryGetProperty("BaseUrl", out var baseUrl) ? baseUrl.GetString() ?? fallback.BaseUrl : fallback.BaseUrl,
            JobsPath = api.TryGetProperty("JobsPath", out var jobsPath) ? jobsPath.GetString() ?? fallback.JobsPath : fallback.JobsPath,
            ReviewPathTemplate = api.TryGetProperty("ReviewPathTemplate", out var reviewPath) ? reviewPath.GetString() ?? fallback.ReviewPathTemplate : fallback.ReviewPathTemplate
        };
    }
}
