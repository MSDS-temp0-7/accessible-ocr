using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

public sealed class HttpAuthenticationService : IAuthenticationService
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly HttpClient _httpClient;
    private readonly OcrApiOptions _options;

    public HttpAuthenticationService(HttpClient httpClient, OcrApiOptions options)
    {
        _httpClient = httpClient;
        _options = options;
    }

    public async Task<AuthenticationSession> LoginAsync(string email, string password, CancellationToken cancellationToken = default)
    {
        using var response = await _httpClient.PostAsJsonAsync(
            _options.LoginPath,
            new LoginRequest(email, password),
            JsonOptions,
            cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            var error = await TryReadErrorAsync(response, cancellationToken);
            throw new AuthenticationServiceException(error ?? "로그인에 실패했습니다. 이메일과 비밀번호를 확인하세요.");
        }

        var result = await response.Content.ReadFromJsonAsync<LoginResponse>(JsonOptions, cancellationToken)
            ?? throw new AuthenticationServiceException("로그인 응답을 읽을 수 없습니다.");

        if (string.IsNullOrWhiteSpace(result.AccessToken) || result.User is null)
        {
            throw new AuthenticationServiceException("로그인 응답에 토큰 또는 사용자 정보가 없습니다.");
        }

        var role = UserRoleExtensions.Parse(result.User.Role);
        var session = new AuthenticationSession(
            result.AccessToken,
            result.RefreshToken ?? string.Empty,
            new AuthenticatedUser(result.User.UserId ?? string.Empty, role, result.User.Name, result.User.Email));

        // 토큰은 디스크에 저장하지 않고 앱 프로세스가 실행되는 동안에만 메모리에 유지한다.
        _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", result.AccessToken);
        return session;
    }

    public void Logout()
    {
        _httpClient.DefaultRequestHeaders.Authorization = null;
    }

    private static async Task<string?> TryReadErrorAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        try
        {
            var error = await response.Content.ReadFromJsonAsync<ErrorResponse>(JsonOptions, cancellationToken);
            return error?.Message;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private sealed record LoginRequest(string Email, string Password);
    private sealed record LoginResponse(string AccessToken, string? RefreshToken, LoginUser? User);
    private sealed record LoginUser(string? UserId, string? Role, string? Name, string? Email);
    private sealed record ErrorResponse(string? ErrorCode, string? Message);
}
