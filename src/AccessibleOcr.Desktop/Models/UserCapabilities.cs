namespace AccessibleOcr.Desktop.Models;

/// <summary>
/// 클라이언트 화면 제어용 권한이다. 실제 보안 판단은 반드시 서버에서도 다시 수행해야 한다.
/// </summary>
public sealed record UserCapabilities(bool CanImport, bool CanReview, bool CanExport)
{
    public static UserCapabilities For(UserRole role) => role switch
    {
        UserRole.Inspector => new UserCapabilities(true, true, true),
        UserRole.Volunteer => new UserCapabilities(false, true, false),
        _ => new UserCapabilities(false, false, false)
    };
}
