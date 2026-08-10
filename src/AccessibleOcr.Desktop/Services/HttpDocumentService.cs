using System.Net.Http.Headers;
using System.Net.Http;
using System.IO;
using System.Text;
using System.Text.Json;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

public sealed class HttpDocumentService : IDocumentService
{
    private readonly HttpClient _httpClient;
    private readonly OcrApiOptions _options;
    private readonly OcrPackageReader _packageReader = new();

    public HttpDocumentService(HttpClient httpClient, OcrApiOptions options)
    {
        _httpClient = httpClient;
        _options = options;
    }

    public async Task<ProcessingJob> SubmitAsync(string filePath, ImportOptions options, CancellationToken cancellationToken = default)
    {
        if (!File.Exists(filePath))
        {
            throw new FileNotFoundException("선택한 PDF 파일을 찾을 수 없습니다.", filePath);
        }

        if (!string.Equals(Path.GetExtension(filePath), ".pdf", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("현재 OCR 파이프라인 입력은 멀티페이지 PDF만 지원합니다.");
        }

        await using var fileStream = File.OpenRead(filePath);
        using var form = new MultipartFormDataContent();
        using var fileContent = new StreamContent(fileStream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/pdf");
        form.Add(fileContent, "file", Path.GetFileName(filePath));
        form.Add(new StringContent(JsonSerializer.Serialize(options), Encoding.UTF8, "application/json"), "options");

        using var response = await _httpClient.PostAsync(_options.JobsPath, form, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
        return ParseJob(json.RootElement);
    }

    public async Task<ProcessingJob> GetJobAsync(string jobId, CancellationToken cancellationToken = default)
    {
        using var response = await _httpClient.GetAsync(BuildJobPath(jobId), cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        using var json = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
        return ParseJob(json.RootElement);
    }

    public async Task<OcrDocumentResult> GetResultAsync(ProcessingJob job, string sourceFileName, CancellationToken cancellationToken = default)
    {
        using var response = await _httpClient.GetAsync($"{BuildJobPath(job.Id)}/result", cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);

        if (response.Content.Headers.ContentType?.MediaType is "application/zip" or "application/x-zip-compressed")
        {
            await using var packageStream = await response.Content.ReadAsStreamAsync(cancellationToken);
            return await _packageReader.ReadAsync(packageStream, sourceFileName, cancellationToken);
        }

        using var json = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
        if (!json.RootElement.TryGetProperty("result_url", out var resultUrl) || resultUrl.GetString() is not { Length: > 0 } url)
        {
            throw new InvalidDataException("결과 API는 ZIP 패키지 또는 result_url을 반환해야 합니다.");
        }

        await using var package = await _httpClient.GetStreamAsync(url, cancellationToken);
        return await _packageReader.ReadAsync(package, sourceFileName, cancellationToken);
    }

    public async Task SaveReviewBlockAsync(string documentId, ReviewBlock block, CancellationToken cancellationToken = default)
    {
        var path = _options.ReviewPathTemplate
            .Replace("{documentId}", Uri.EscapeDataString(documentId), StringComparison.Ordinal)
            .Replace("{elementId}", Uri.EscapeDataString(block.Id), StringComparison.Ordinal);
        var payload = new
        {
            corrected_content = block.Content,
            review_status = block.ReviewStatus.ToString().ToLowerInvariant(),
            revision = block.Revision
        };

        using var request = new HttpRequestMessage(HttpMethod.Patch, path)
        {
            Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json")
        };
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
    }

    private string BuildJobPath(string jobId) => $"{_options.JobsPath.TrimEnd('/')}/{Uri.EscapeDataString(jobId)}";

    private static ProcessingJob ParseJob(JsonElement root)
    {
        var jobId = GetString(root, "job_id") ?? GetString(root, "jobId") ?? throw new InvalidDataException("Job 응답에 job_id가 없습니다.");
        return new ProcessingJob(
            jobId,
            GetString(root, "status") ?? "queued",
            GetInt(root, "progress"),
            GetString(root, "message"),
            GetString(root, "document_id") ?? GetString(root, "documentId"),
            GetString(root, "error"));
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        throw new HttpRequestException($"OCR API 요청 실패: {(int)response.StatusCode} {response.ReasonPhrase}. {body}");
    }

    private static int? GetInt(JsonElement root, string propertyName)
        => root.TryGetProperty(propertyName, out var value) && value.TryGetInt32(out var number) ? number : null;

    private static string? GetString(JsonElement root, string propertyName)
        => root.TryGetProperty(propertyName, out var value) ? value.GetString() : null;
}
