using System.Net.Mail;
using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class SignUpViewModel : ObservableObject
{
    private readonly Action _backToLogin;
    private string _name = string.Empty;
    private string _email = string.Empty;
    private string _password = string.Empty;
    private string _passwordConfirmation = string.Empty;
    private RegistrationRoleOption _selectedRole;
    private string _statusMessage = "입력한 정보는 아직 서버나 DB에 저장되지 않습니다.";

    public SignUpViewModel(Action backToLogin)
    {
        _backToLogin = backToLogin;
        RoleOptions =
        [
            new RegistrationRoleOption(UserRole.Reader, "리더", "완성된 접근형 문서를 읽고 내려받는 사용자"),
            new RegistrationRoleOption(UserRole.Volunteer, "자원봉사자", "할당된 문서의 인식 결과를 검수하는 사용자")
        ];
        _selectedRole = RoleOptions[0];

        SubmitCommand = new RelayCommand(_ => PrepareRegistration(), _ => HasRequiredFields());
        BackToLoginCommand = new RelayCommand(_ => _backToLogin());
    }

    public IReadOnlyList<RegistrationRoleOption> RoleOptions { get; }

    public string Name
    {
        get => _name;
        set => SetAndRefresh(ref _name, value);
    }

    public string Email
    {
        get => _email;
        set => SetAndRefresh(ref _email, value);
    }

    public string Password
    {
        get => _password;
        set => SetAndRefresh(ref _password, value);
    }

    public string PasswordConfirmation
    {
        get => _passwordConfirmation;
        set => SetAndRefresh(ref _passwordConfirmation, value);
    }

    public RegistrationRoleOption SelectedRole
    {
        get => _selectedRole;
        set => SetAndRefresh(ref _selectedRole, value);
    }

    public string StatusMessage
    {
        get => _statusMessage;
        private set => SetProperty(ref _statusMessage, value);
    }

    public RelayCommand SubmitCommand { get; }
    public RelayCommand BackToLoginCommand { get; }

    public void Reset()
    {
        Name = string.Empty;
        Email = string.Empty;
        Password = string.Empty;
        PasswordConfirmation = string.Empty;
        SelectedRole = RoleOptions[0];
        StatusMessage = "입력한 정보는 아직 서버나 DB에 저장되지 않습니다.";
    }

    private bool HasRequiredFields() =>
        !string.IsNullOrWhiteSpace(Name)
        && !string.IsNullOrWhiteSpace(Email)
        && !string.IsNullOrWhiteSpace(Password)
        && !string.IsNullOrWhiteSpace(PasswordConfirmation);

    private void PrepareRegistration()
    {
        if (!MailAddress.TryCreate(Email.Trim(), out _))
        {
            StatusMessage = "올바른 이메일 주소를 입력하세요.";
            return;
        }

        if (Password.Length < 8)
        {
            StatusMessage = "비밀번호는 8자 이상이어야 합니다.";
            return;
        }

        if (!string.Equals(Password, PasswordConfirmation, StringComparison.Ordinal))
        {
            StatusMessage = "비밀번호와 비밀번호 확인이 일치하지 않습니다.";
            return;
        }

        // 추후 회원가입 API 계약이 확정되면 이 DTO를 IRegistrationService로 전달한다.
        _ = new RegistrationDraft(Name.Trim(), Email.Trim(), Password, SelectedRole.Role);
        StatusMessage = "회원가입 서버와 DB가 아직 연결되지 않아 저장하지 않았습니다. 입력 형식만 확인되었습니다.";
    }

    private void SetAndRefresh<T>(ref T field, T value)
    {
        if (SetProperty(ref field, value))
        {
            SubmitCommand.RaiseCanExecuteChanged();
        }
    }
}

public sealed record RegistrationRoleOption(UserRole Role, string DisplayName, string Description);
