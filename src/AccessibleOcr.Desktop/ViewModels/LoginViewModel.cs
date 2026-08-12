using System.Net.Http;
using System.Windows;
using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Services;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class LoginViewModel : ObservableObject
{
    private readonly IAuthenticationService _authenticationService;
    private readonly Action<Models.AuthenticationSession> _onAuthenticated;
    private readonly Action _openSignUp;
    private readonly Action _onDevelopmentPreview;
    private string _email = string.Empty;
    private string _password = string.Empty;
    private string _statusMessage = "등록된 계정으로 로그인하세요.";

    public LoginViewModel(
        IAuthenticationService authenticationService,
        Action<Models.AuthenticationSession> onAuthenticated,
        Action openSignUp,
        Action onDevelopmentPreview)
    {
        _authenticationService = authenticationService;
        _onAuthenticated = onAuthenticated;
        _openSignUp = openSignUp;
        _onDevelopmentPreview = onDevelopmentPreview;
        LoginCommand = new AsyncRelayCommand(_ => LoginAsync(), _ => CanLogin());
        OpenSignUpCommand = new RelayCommand(_ => _openSignUp());
        DevelopmentPreviewCommand = new RelayCommand(_ => _onDevelopmentPreview(), _ => CanUseDevelopmentPreview);
    }

    public string Email
    {
        get => _email;
        set
        {
            if (SetProperty(ref _email, value))
            {
                LoginCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public string Password
    {
        get => _password;
        set
        {
            if (SetProperty(ref _password, value))
            {
                LoginCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public string StatusMessage
    {
        get => _statusMessage;
        private set => SetProperty(ref _statusMessage, value);
    }

#if DEBUG
    public bool CanUseDevelopmentPreview => true;
#else
    public bool CanUseDevelopmentPreview => false;
#endif

    public Visibility DevelopmentPreviewVisibility => CanUseDevelopmentPreview ? Visibility.Visible : Visibility.Collapsed;
    public AsyncRelayCommand LoginCommand { get; }
    public RelayCommand OpenSignUpCommand { get; }
    public RelayCommand DevelopmentPreviewCommand { get; }

    public void Reset()
    {
        Password = string.Empty;
        StatusMessage = "로그아웃되었습니다.";
    }

    private bool CanLogin() => !string.IsNullOrWhiteSpace(Email) && !string.IsNullOrWhiteSpace(Password);

    private async Task LoginAsync()
    {
        StatusMessage = "인증 서버에 로그인하는 중입니다.";
        try
        {
            var session = await _authenticationService.LoginAsync(Email.Trim(), Password);
            Password = string.Empty;
            _onAuthenticated(session);
        }
        catch (AuthenticationServiceException exception)
        {
            StatusMessage = exception.Message;
        }
        catch (HttpRequestException)
        {
            StatusMessage = "인증 서버에 연결할 수 없습니다. 통합 API 실행 상태를 확인하세요.";
        }
        catch (TaskCanceledException)
        {
            StatusMessage = "로그인 요청 시간이 초과되었습니다.";
        }
    }
}
