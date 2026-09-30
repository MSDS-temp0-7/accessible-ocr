using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Text;
using System.Xml;
using System.Xml.Linq;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

/// <summary>
/// 검수 작업공간에 로드된 문서를 외부 서버 없이 로컬 파일로 내보낸다.
/// DOCX는 OOXML 패키지를 직접 만들고, HWPX는 설치된 한/글의 공식 COM
/// 자동화 인터페이스를 사용해 호환 문서를 생성한다.
/// </summary>
public sealed class DocumentExporter : IDocumentExporter
{
    private static readonly XNamespace Word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
    private static readonly XNamespace Relationship = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

    public Task ExportDocxAsync(
        OcrDocumentResult result,
        string destinationPath,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        ValidateDestination(destinationPath, ".docx");
        WriteAtomically(
            destinationPath,
            temporaryPath =>
            {
                using var stream = new FileStream(temporaryPath, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None);
                using var archive = new ZipArchive(stream, ZipArchiveMode.Create, leaveOpen: false);

                WriteXml(archive, "[Content_Types].xml", BuildContentTypes());
                WriteXml(archive, "_rels/.rels", BuildPackageRelationships());
                WriteXml(archive, "docProps/core.xml", BuildCoreProperties(result));
                WriteXml(archive, "docProps/app.xml", BuildAppProperties());
                WriteXml(archive, "word/document.xml", BuildWordDocument(result));
                WriteXml(archive, "word/styles.xml", BuildWordStyles());
                WriteXml(archive, "word/_rels/document.xml.rels", BuildDocumentRelationships());
            });
        return Task.CompletedTask;
    }

    public Task ExportHwpxAsync(
        OcrDocumentResult result,
        string destinationPath,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        ValidateDestination(destinationPath, ".hwpx");
        WriteAtomically(
            destinationPath,
            temporaryPath => ExportWithHancomOffice(result, temporaryPath));
        return Task.CompletedTask;
    }

    public Task<DaisyExportOutcome> ExportDaisy3Async(
        OcrDocumentResult result,
        string destinationPath,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(Daisy3Exporter.Export(result, destinationPath));
    }

    private static void ExportWithHancomOffice(OcrDocumentResult result, string destinationPath)
    {
        var hwpType = Type.GetTypeFromProgID("HWPFrame.HwpObject")
            ?? throw new InvalidOperationException(
                "HWPX 내보내기에는 한컴오피스 한/글 2010 이상이 필요합니다. " +
                "한/글을 설치한 뒤 다시 시도하거나 DOCX로 내보내세요.");
        object? rawObject = null;
        try
        {
            rawObject = Activator.CreateInstance(hwpType)
                ?? throw new InvalidOperationException("한/글 자동화 개체를 시작하지 못했습니다.");
            dynamic hwp = rawObject;
            hwp.XHwpWindows.Item(0).Visible = false;
            hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet);
            hwp.HParameterSet.HInsertText.Text = BuildPlainText(result);
            if (!(bool)hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet))
            {
                throw new InvalidOperationException("한/글 문서에 검수 결과를 입력하지 못했습니다.");
            }

            if (!(bool)hwp.SaveAs(Path.GetFullPath(destinationPath), "HWPX", string.Empty))
            {
                throw new InvalidOperationException("한/글이 HWPX 파일을 저장하지 못했습니다.");
            }
        }
        catch (COMException exception)
        {
            throw new InvalidOperationException(
                "한/글 자동화 중 오류가 발생했습니다. 한/글 설치 상태와 파일 저장 권한을 확인하세요.",
                exception);
        }
        finally
        {
            if (rawObject is not null)
            {
                try
                {
                    ((dynamic)rawObject).Quit();
                }
                catch
                {
                    // 저장 오류가 발생해도 숨겨진 한/글 프로세스 정리를 계속한다.
                }

                if (Marshal.IsComObject(rawObject))
                {
                    Marshal.FinalReleaseComObject(rawObject);
                }
            }
        }
    }

    private static string BuildPlainText(OcrDocumentResult result)
    {
        var builder = new StringBuilder();
        builder.AppendLine(result.Document.Title);
        builder.AppendLine();

        var currentPage = 0;
        foreach (var block in OrderedBlocks(result))
        {
            if (block.PageNumber != currentPage)
            {
                if (currentPage != 0)
                {
                    builder.AppendLine();
                }

                currentPage = block.PageNumber;
                builder.AppendLine($"{currentPage}페이지");
            }

            if (block.Type != BlockType.Text)
            {
                builder.Append($"[{block.TypeDisplayName}] ");
            }

            builder.AppendLine(block.Content.Trim());
            if (block.ReviewStatus != ReviewStatus.Reviewed)
            {
                builder.AppendLine($"[검수 상태: {ReviewStatusText(block.ReviewStatus)}]");
            }
        }

        return builder.ToString();
    }

    private static XDocument BuildWordDocument(OcrDocumentResult result)
    {
        var body = new XElement(Word + "body");
        body.Add(Paragraph(result.Document.Title, "Title"));

        var currentPage = 0;
        foreach (var block in OrderedBlocks(result))
        {
            if (block.PageNumber != currentPage)
            {
                currentPage = block.PageNumber;
                body.Add(Paragraph($"{currentPage}페이지", "Heading1"));
            }

            var content = block.Type == BlockType.Text
                ? block.Content.Trim()
                : $"[{block.TypeDisplayName}] {block.Content.Trim()}";
            body.Add(Paragraph(content, "Normal"));

            if (block.ReviewStatus != ReviewStatus.Reviewed)
            {
                body.Add(Paragraph(
                    $"검수 상태: {ReviewStatusText(block.ReviewStatus)}",
                    "ReviewNote"));
            }
        }

        body.Add(
            new XElement(
                Word + "sectPr",
                new XElement(Word + "pgSz", new XAttribute(Word + "w", "11906"), new XAttribute(Word + "h", "16838")),
                new XElement(
                    Word + "pgMar",
                    new XAttribute(Word + "top", "1440"),
                    new XAttribute(Word + "right", "1440"),
                    new XAttribute(Word + "bottom", "1440"),
                    new XAttribute(Word + "left", "1440"),
                    new XAttribute(Word + "header", "720"),
                    new XAttribute(Word + "footer", "720"),
                    new XAttribute(Word + "gutter", "0"))));

        return XmlDocument(
            new XElement(
                Word + "document",
                new XAttribute(XNamespace.Xmlns + "w", Word),
                new XAttribute(XNamespace.Xmlns + "r", Relationship),
                body));
    }

    private static XElement Paragraph(string text, string style)
    {
        var paragraph = new XElement(
            Word + "p",
            new XElement(Word + "pPr", new XElement(Word + "pStyle", new XAttribute(Word + "val", style))));
        var pieces = text.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n').Split('\n');
        for (var index = 0; index < pieces.Length; index++)
        {
            if (index > 0)
            {
                paragraph.Add(new XElement(Word + "r", new XElement(Word + "br")));
            }

            paragraph.Add(
                new XElement(
                    Word + "r",
                    new XElement(
                        Word + "t",
                        new XAttribute(XNamespace.Xml + "space", "preserve"),
                        pieces[index])));
        }

        return paragraph;
    }

    private static XDocument BuildWordStyles()
    {
        XElement Style(string id, string name, int size, bool bold = false, string? color = null)
        {
            var runProperties = new XElement(
                Word + "rPr",
                new XElement(
                    Word + "rFonts",
                    new XAttribute(Word + "ascii", "Malgun Gothic"),
                    new XAttribute(Word + "hAnsi", "Malgun Gothic"),
                    new XAttribute(Word + "eastAsia", "맑은 고딕")),
                new XElement(Word + "sz", new XAttribute(Word + "val", size.ToString())),
                new XElement(Word + "szCs", new XAttribute(Word + "val", size.ToString())),
                new XElement(Word + "lang", new XAttribute(Word + "val", "ko-KR")));
            if (bold)
            {
                runProperties.Add(new XElement(Word + "b"));
            }
            if (color is not null)
            {
                runProperties.Add(new XElement(Word + "color", new XAttribute(Word + "val", color)));
            }

            return new XElement(
                Word + "style",
                new XAttribute(Word + "type", "paragraph"),
                new XAttribute(Word + "styleId", id),
                id == "Normal" ? new XAttribute(Word + "default", "1") : null,
                new XElement(Word + "name", new XAttribute(Word + "val", name)),
                id != "Normal" ? new XElement(Word + "basedOn", new XAttribute(Word + "val", "Normal")) : null,
                id.StartsWith("Heading", StringComparison.Ordinal)
                    ? new XElement(Word + "qFormat")
                    : null,
                runProperties);
        }

        return XmlDocument(
            new XElement(
                Word + "styles",
                new XAttribute(XNamespace.Xmlns + "w", Word),
                new XElement(
                    Word + "docDefaults",
                    new XElement(
                        Word + "rPrDefault",
                        new XElement(
                            Word + "rPr",
                            new XElement(
                                Word + "rFonts",
                                new XAttribute(Word + "ascii", "Malgun Gothic"),
                                new XAttribute(Word + "hAnsi", "Malgun Gothic"),
                                new XAttribute(Word + "eastAsia", "맑은 고딕")),
                            new XElement(Word + "lang", new XAttribute(Word + "val", "ko-KR"))))),
                Style("Normal", "표준", 22),
                Style("Title", "제목", 36, bold: true, color: "0C355B"),
                Style("Heading1", "제목 1", 28, bold: true, color: "10385D"),
                Style("ReviewNote", "검수 상태", 18, color: "9C5700")));
    }

    private static XDocument BuildContentTypes()
    {
        XNamespace contentType = "http://schemas.openxmlformats.org/package/2006/content-types";
        return XmlDocument(
            new XElement(
                contentType + "Types",
                new XElement(contentType + "Default", new XAttribute("Extension", "rels"), new XAttribute("ContentType", "application/vnd.openxmlformats-package.relationships+xml")),
                new XElement(contentType + "Default", new XAttribute("Extension", "xml"), new XAttribute("ContentType", "application/xml")),
                new XElement(contentType + "Override", new XAttribute("PartName", "/word/document.xml"), new XAttribute("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")),
                new XElement(contentType + "Override", new XAttribute("PartName", "/word/styles.xml"), new XAttribute("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml")),
                new XElement(contentType + "Override", new XAttribute("PartName", "/docProps/core.xml"), new XAttribute("ContentType", "application/vnd.openxmlformats-package.core-properties+xml")),
                new XElement(contentType + "Override", new XAttribute("PartName", "/docProps/app.xml"), new XAttribute("ContentType", "application/vnd.openxmlformats-officedocument.extended-properties+xml"))));
    }

    private static XDocument BuildPackageRelationships()
    {
        XNamespace relationships = "http://schemas.openxmlformats.org/package/2006/relationships";
        return XmlDocument(
            new XElement(
                relationships + "Relationships",
                RelationshipElement(relationships, "rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "word/document.xml"),
                RelationshipElement(relationships, "rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
                RelationshipElement(relationships, "rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml")));
    }

    private static XDocument BuildDocumentRelationships()
    {
        XNamespace relationships = "http://schemas.openxmlformats.org/package/2006/relationships";
        return XmlDocument(
            new XElement(
                relationships + "Relationships",
                RelationshipElement(relationships, "rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml")));
    }

    private static XElement RelationshipElement(XNamespace ns, string id, string type, string target)
        => new(
            ns + "Relationship",
            new XAttribute("Id", id),
            new XAttribute("Type", type),
            new XAttribute("Target", target));

    private static XDocument BuildCoreProperties(OcrDocumentResult result)
    {
        XNamespace core = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties";
        XNamespace dc = "http://purl.org/dc/elements/1.1/";
        XNamespace dcterms = "http://purl.org/dc/terms/";
        XNamespace xsi = "http://www.w3.org/2001/XMLSchema-instance";
        var now = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
        return XmlDocument(
            new XElement(
                core + "coreProperties",
                new XAttribute(XNamespace.Xmlns + "cp", core),
                new XAttribute(XNamespace.Xmlns + "dc", dc),
                new XAttribute(XNamespace.Xmlns + "dcterms", dcterms),
                new XAttribute(XNamespace.Xmlns + "xsi", xsi),
                new XElement(dc + "title", result.Document.Title),
                new XElement(dc + "creator", "Accessible OCR"),
                new XElement(core + "lastModifiedBy", "Accessible OCR"),
                new XElement(dc + "language", "ko-KR"),
                new XElement(dcterms + "created", new XAttribute(xsi + "type", "dcterms:W3CDTF"), now),
                new XElement(dcterms + "modified", new XAttribute(xsi + "type", "dcterms:W3CDTF"), now)));
    }

    private static XDocument BuildAppProperties()
    {
        XNamespace extended = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties";
        XNamespace vector = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes";
        return XmlDocument(
            new XElement(
                extended + "Properties",
                new XAttribute(XNamespace.Xmlns + "vt", vector),
                new XElement(extended + "Application", "Accessible OCR"),
                new XElement(extended + "AppVersion", "1.0")));
    }

    private static XDocument XmlDocument(XElement root)
        => new(new XDeclaration("1.0", "UTF-8", "yes"), root);

    private static void WriteXml(ZipArchive archive, string path, XDocument document)
    {
        var entry = archive.CreateEntry(path, CompressionLevel.Optimal);
        using var stream = entry.Open();
        using var writer = XmlWriter.Create(
            stream,
            new XmlWriterSettings
            {
                Encoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false),
                Indent = false,
                CloseOutput = false
            });
        document.Save(writer);
    }

    private static IEnumerable<ReviewBlock> OrderedBlocks(OcrDocumentResult result)
        => result.Blocks
            .OrderBy(block => block.PageNumber)
            .ThenBy(block => block.Y)
            .ThenBy(block => block.X);

    private static string ReviewStatusText(ReviewStatus status) => status switch
    {
        ReviewStatus.Reviewed => "검수 완료",
        ReviewStatus.NeedsReview => "검수 필요",
        _ => "미확인"
    };

    private static void ValidateDestination(string destinationPath, string expectedExtension)
    {
        if (string.IsNullOrWhiteSpace(destinationPath))
        {
            throw new ArgumentException("저장 경로가 비어 있습니다.", nameof(destinationPath));
        }

        if (!string.Equals(Path.GetExtension(destinationPath), expectedExtension, StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException($"{expectedExtension} 확장자로 저장해야 합니다.", nameof(destinationPath));
        }
    }

    private static void WriteAtomically(string destinationPath, Action<string> write)
    {
        var fullPath = Path.GetFullPath(destinationPath);
        var directory = Path.GetDirectoryName(fullPath)
            ?? throw new ArgumentException("저장 폴더를 확인할 수 없습니다.", nameof(destinationPath));
        var extension = Path.GetExtension(fullPath);
        var temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileNameWithoutExtension(fullPath)}.{Guid.NewGuid():N}{extension}");

        try
        {
            write(temporaryPath);
            File.Move(temporaryPath, fullPath, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }
}
