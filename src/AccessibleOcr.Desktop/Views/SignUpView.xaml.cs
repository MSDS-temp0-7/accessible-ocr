using System.Windows.Controls;
using AccessibleOcr.Desktop.ViewModels;

namespace AccessibleOcr.Desktop.Views;

public partial class SignUpView : UserControl
{
    public SignUpView()
    {
        InitializeComponent();
    }

    private void PasswordBox_OnPasswordChanged(object sender, System.Windows.RoutedEventArgs e)
    {
        if (DataContext is SignUpViewModel viewModel && sender is PasswordBox passwordBox)
        {
            viewModel.Password = passwordBox.Password;
        }
    }

    private void PasswordConfirmationBox_OnPasswordChanged(object sender, System.Windows.RoutedEventArgs e)
    {
        if (DataContext is SignUpViewModel viewModel && sender is PasswordBox passwordBox)
        {
            viewModel.PasswordConfirmation = passwordBox.Password;
        }
    }
}
