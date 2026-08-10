namespace AccessibleOcr.Desktop.Models;

public sealed class ImportOptions
{
    public string PageRange { get; set; } = "전체 페이지";
    public string Language { get; set; } = "한국어";
    public bool DetectBody { get; set; } = true;
    public bool DetectTables { get; set; } = true;
    public bool DetectCharts { get; set; } = true;
    public bool DetectMath { get; set; } = true;
    public bool DetectMusic { get; set; } = true;
    public bool DetectImages { get; set; } = true;
    public string ProcessingPolicy { get; set; } = "조직 정책에 따라 처리";
}
