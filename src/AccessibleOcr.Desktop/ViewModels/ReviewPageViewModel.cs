using System.IO;
using System.Windows.Media.Imaging;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

public sealed class ReviewPageViewModel
{
    public const double PreviewMaxWidth = 760;

    public ReviewPageViewModel(OcrPage page)
    {
        PageNumber = page.PageIndex + 1;
        Width = Math.Max(1, page.Width);
        Height = Math.Max(1, page.Height);
        Dpi = page.Dpi;
        DisplayScale = Math.Min(1, PreviewMaxWidth / Width);
        DisplayWidth = Width * DisplayScale;
        DisplayHeight = Height * DisplayScale;
        ImageSource = CreateImage(page.ImageBytes);
    }

    public int PageNumber { get; }
    public int Width { get; }
    public int Height { get; }
    public int Dpi { get; }
    public double DisplayScale { get; }
    public double DisplayWidth { get; }
    public double DisplayHeight { get; }
    public BitmapSource? ImageSource { get; }
    public bool HasImage => ImageSource is not null;
    public string DisplayName => $"{PageNumber}페이지";

    private static BitmapSource? CreateImage(byte[]? bytes)
    {
        if (bytes is not { Length: > 0 })
        {
            return null;
        }

        using var stream = new MemoryStream(bytes, writable: false);
        var image = new BitmapImage();
        image.BeginInit();
        image.CacheOption = BitmapCacheOption.OnLoad;
        image.StreamSource = stream;
        image.EndInit();
        image.Freeze();
        return image;
    }
}
