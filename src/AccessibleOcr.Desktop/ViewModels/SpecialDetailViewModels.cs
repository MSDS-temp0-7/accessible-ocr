using AccessibleOcr.Desktop.Infrastructure;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.ViewModels;

public abstract class SpecialDetailViewModelBase : ObservableObject
{
    private ReviewBlock? _selectedBlock;

    public ReviewBlock? SelectedBlock
    {
        get => _selectedBlock;
        private set => SetProperty(ref _selectedBlock, value);
    }

    public void Load(ReviewBlock block) => SelectedBlock = block;
}

public sealed class TableDetailViewModel : SpecialDetailViewModelBase
{
}

public sealed class MathDetailViewModel : SpecialDetailViewModelBase
{
}

public sealed class MusicDetailViewModel : SpecialDetailViewModelBase
{
}
