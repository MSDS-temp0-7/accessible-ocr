namespace AccessibleOcr.Desktop.Models;

public sealed record AuthenticatedUser(string UserId, UserRole Role, string? Name = null, string? Email = null);

public sealed record AuthenticationSession(
    string AccessToken,
    string RefreshToken,
    AuthenticatedUser User,
    bool IsDevelopmentPreview = false);
