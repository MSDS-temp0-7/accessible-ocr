namespace AccessibleOcr.Desktop.Models;

/// <summary>
/// 회원가입 API 계약을 연결할 때 사용할 클라이언트 입력 모델이다.
/// 현재는 서버나 DB로 전송·저장하지 않는다.
/// </summary>
public sealed record RegistrationDraft(
    string Name,
    string Email,
    string Password,
    UserRole RequestedRole);
