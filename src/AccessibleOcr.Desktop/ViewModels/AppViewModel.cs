using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;
using AccessibleOcr.Desktop.Services;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class AppViewModel : ObservableObject
{
    private readonly IAuthenticationService _authenticationService;
    private readonly IDocumentService _documentService;
    private readonly IFilePicker _filePicker;
    private object _currentView;
    private MainViewModel? _main;
    private AuthenticationSession? _session;

    public AppViewModel(
        IAuthenticationService authenticationService,
        IDocumentService documentService,
        IFilePicker filePicker)
    {
        _authenticationService = authenticationService;
        _documentService = documentService;
        _filePicker = filePicker;
        Login = new LoginViewModel(authenticationService, CompleteLogin, OpenSignUp, EnterDevelopmentPreview);
        SignUp = new SignUpViewModel(ReturnToLogin);
        _currentView = Login;

        NavigateCommand = new RelayCommand(
            parameter => Main?.NavigateCommand.Execute(parameter),
            parameter => Main?.NavigateCommand.CanExecute(parameter) ?? false);
        StartAnalysisCommand = new RelayCommand(
            parameter => Main?.StartAnalysisCommand.Execute(parameter),
            parameter => Main?.StartAnalysisCommand.CanExecute(parameter) ?? false);
        LogoutCommand = new RelayCommand(_ => Logout(), _ => Session is not null);
    }

    public LoginViewModel Login { get; }
    public SignUpViewModel SignUp { get; }

    public MainViewModel? Main
    {
        get => _main;
        private set => SetProperty(ref _main, value);
    }

    public AuthenticationSession? Session
    {
        get => _session;
        private set
        {
            if (SetProperty(ref _session, value))
            {
                OnPropertyChanged(nameof(CurrentUserLabel));
                OnPropertyChanged(nameof(SessionStatusLabel));
                LogoutCommand.RaiseCanExecuteChanged();
            }
        }
    }

    public object CurrentView
    {
        get => _currentView;
        private set => SetProperty(ref _currentView, value);
    }

    public string CurrentUserLabel => Session is null
        ? "로그인 필요"
        : $"{Session.User.Name ?? Session.User.Email ?? Session.User.UserId} · {Session.User.Role.ToDisplayName()}";

    public string SessionStatusLabel => Session?.IsDevelopmentPreview == true
        ? "개발 미리보기 · 서버 권한 미검증"
        : "인증됨";

    public RelayCommand NavigateCommand { get; }
    public RelayCommand StartAnalysisCommand { get; }
    public RelayCommand LogoutCommand { get; }

    private void CompleteLogin(AuthenticationSession session)
    {
        Session = session;
        Main = new MainViewModel(_documentService, _filePicker, session.User);
        CurrentView = Main;
        RaiseMainCommandState();
    }

    private void EnterDevelopmentPreview()
    {
#if DEBUG
        CompleteLogin(new AuthenticationSession(
            string.Empty,
            string.Empty,
            new AuthenticatedUser("development-preview", UserRole.Inspector, "개발 미리보기"),
            true));
#endif
    }

    private void OpenSignUp()
    {
        SignUp.Reset();
        CurrentView = SignUp;
    }

    private void ReturnToLogin()
    {
        CurrentView = Login;
    }

    private void Logout()
    {
        _authenticationService.Logout();
        Session = null;
        Main = null;
        Login.Reset();
        CurrentView = Login;
        RaiseMainCommandState();
    }

    private void RaiseMainCommandState()
    {
        NavigateCommand.RaiseCanExecuteChanged();
        StartAnalysisCommand.RaiseCanExecuteChanged();
    }
}
