using System.Text.Json;
using System.IO;

namespace AccessibleOcr.Desktop.Services;

public sealed class OcrApiOptions
{
    // 이 주소는 CLOVA OCR 주소가 아니라 우리 통합 API 주소다.
    // CLOVA X-OCR-SECRET은 EXE에서 읽거나 전송하지 않고 통합 서버에만 둔다.
    public string BaseUrl { get; init; } = "http://localhost:8000";
    public string JobsPath { get; init; } = "/api/v1/jobs";
    public string ReviewPathTemplate { get; init; } = "/api/v1/documents/{documentId}/elements/{elementId}/review";
    public string LoginPath { get; init; } = "/auth/login";

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
        var hasApi = json.RootElement.TryGetProperty("OcrApi", out var api);
        var hasAuthentication = json.RootElement.TryGetProperty("Authentication", out var authentication);

        return new OcrApiOptions
        {
            BaseUrl = hasApi && api.TryGetProperty("BaseUrl", out var baseUrl) ? baseUrl.GetString() ?? fallback.BaseUrl : fallback.BaseUrl,
            JobsPath = hasApi && api.TryGetProperty("JobsPath", out var jobsPath) ? jobsPath.GetString() ?? fallback.JobsPath : fallback.JobsPath,
            ReviewPathTemplate = hasApi && api.TryGetProperty("ReviewPathTemplate", out var reviewPath) ? reviewPath.GetString() ?? fallback.ReviewPathTemplate : fallback.ReviewPathTemplate,
            LoginPath = hasAuthentication && authentication.TryGetProperty("LoginPath", out var loginPath) ? loginPath.GetString() ?? fallback.LoginPath : fallback.LoginPath
        };
    }
}
