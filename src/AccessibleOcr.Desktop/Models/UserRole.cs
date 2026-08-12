namespace AccessibleOcr.Desktop.Models;

public enum UserRole
{
    Unknown,
    Reader,
    Inspector,
    Volunteer
}

public static class UserRoleExtensions
{
    public static UserRole Parse(string? value) => value?.ToUpperInvariant() switch
    {
        "READER" => UserRole.Reader,
        "INSPECTOR" => UserRole.Inspector,
        "VOLUNTEER" => UserRole.Volunteer,
        _ => UserRole.Unknown
    };

    public static string ToDisplayName(this UserRole role) => role switch
    {
        UserRole.Reader => "리더",
        UserRole.Inspector => "기관 검수자",
        UserRole.Volunteer => "자원봉사 검수자",
        _ => "권한 미확인"
    };
}
