using AccessibleOcr.Desktop.Services;
using AccessibleOcr.Desktop.ViewModels;
using System.Net.Http;

namespace AccessibleOcr.Desktop;

public partial class MainWindow : System.Windows.Window
{
    public MainWindow()
    {
        InitializeComponent();
        var options = OcrApiOptions.Load();
        var httpClient = new HttpClient { BaseAddress = new Uri(options.BaseUrl) };
        DataContext = new AppViewModel(
            new HttpAuthenticationService(httpClient, options),
            new HttpDocumentService(httpClient, options),
            new WindowsFilePicker());
    }
}
