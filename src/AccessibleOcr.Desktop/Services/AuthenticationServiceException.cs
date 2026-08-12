namespace AccessibleOcr.Desktop.Services;

public sealed class AuthenticationServiceException : Exception
{
    public AuthenticationServiceException(string message) : base(message)
    {
    }
}
