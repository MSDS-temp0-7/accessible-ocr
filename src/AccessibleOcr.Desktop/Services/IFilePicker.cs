namespace AccessibleOcr.Desktop.Services;

public interface IFilePicker
{
    Task<string?> PickPdfAsync();
}

