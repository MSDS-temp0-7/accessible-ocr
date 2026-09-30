namespace AccessibleOcr.Desktop.Services;

public interface IFilePicker
{
    Task<string?> PickPdfAsync();

    Task<string?> PickSaveFileAsync(
        string title,
        string suggestedFileName,
        string filter,
        string defaultExtension);
}

