using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

public interface IAuthenticationService
{
    Task<AuthenticationSession> LoginAsync(string email, string password, CancellationToken cancellationToken = default);
    void Logout();
}
