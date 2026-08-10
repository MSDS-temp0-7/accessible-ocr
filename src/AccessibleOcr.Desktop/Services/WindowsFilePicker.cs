using Microsoft.Win32;

namespace AccessibleOcr.Desktop.Services;

public sealed class WindowsFilePicker : IFilePicker
{
    public Task<string?> PickPdfAsync()
    {
        var dialog = new OpenFileDialog
        {
            Title = "OCR 분석할 PDF 선택",
            Filter = "PDF 문서 (*.pdf)|*.pdf",
            CheckFileExists = true,
            Multiselect = false
        };

        return Task.FromResult(dialog.ShowDialog() == true ? dialog.FileName : null);
    }
}

