using System.Windows;
using System.Windows.Input;

namespace AccessibleOcr.Desktop.Views;

public partial class ImportSettingsView : System.Windows.Controls.UserControl
{
    public ImportSettingsView()
    {
        InitializeComponent();
    }

    private void PageNumberTextBox_OnPreviewTextInput(object sender, TextCompositionEventArgs eventArgs)
    {
        eventArgs.Handled = eventArgs.Text.Any(character => !char.IsDigit(character));
    }

    private void PageNumberTextBox_OnPasting(object sender, DataObjectPastingEventArgs eventArgs)
    {
        if (!eventArgs.DataObject.GetDataPresent(DataFormats.UnicodeText))
        {
            eventArgs.CancelCommand();
            return;
        }

        var text = eventArgs.DataObject.GetData(DataFormats.UnicodeText) as string;
        if (string.IsNullOrEmpty(text) || text.Any(character => !char.IsDigit(character)))
        {
            eventArgs.CancelCommand();
        }
    }
}
