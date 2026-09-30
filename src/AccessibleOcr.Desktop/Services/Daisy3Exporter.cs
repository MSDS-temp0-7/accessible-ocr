using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Xml;
using System.Xml.Linq;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

/// <summary>
/// ANSI/NISO Z39.86-2005(R2012)의 textNCX 유형 DAISY3 패키지를 생성한다.
/// 현재 OCR 결과가 오디오를 제공하지 않으므로 SMIL은 DTBook 텍스트 조각만
/// 연결한다. 완성 전에 필수 파일, 매니페스트와 내부 fragment 참조를 검사한다.
/// </summary>
internal static class Daisy3Exporter
{
    private const string PackageFileName = "package.opf";
    private const string DtbookFileName = "book.xml";
    private const string NcxFileName = "navigation.ncx";
    private const string SmilFileName = "book.smil";

    private static readonly XNamespace Package = "http://openebook.org/namespaces/oeb-package/1.0/";
    private static readonly XNamespace DublinCore = "http://purl.org/dc/elements/1.1/";
    private static readonly XNamespace Dtbook = "http://www.daisy.org/z3986/2005/dtbook/";
    private static readonly XNamespace Ncx = "http://www.daisy.org/z3986/2005/ncx/";
    private static readonly XNamespace Smil = "http://www.w3.org/2001/SMIL20/";

    public static DaisyExportOutcome Export(OcrDocumentResult result, string destinationPath)
    {
        ValidateDestination(destinationPath);
        var fullPackagePath = Path.GetFullPath(destinationPath);
        var directory = Path.GetDirectoryName(fullPackagePath)
            ?? throw new ArgumentException("저장 폴더를 확인할 수 없습니다.", nameof(destinationPath));
        var reportPath = Path.Combine(
            directory,
            $"{Path.GetFileNameWithoutExtension(fullPackagePath)}-검수보고서.html");
        var packageTemporaryPath = TemporaryPath(fullPackagePath);
        var reportTemporaryPath = TemporaryPath(reportPath);
        var model = CreateModel(result);

        try
        {
            WritePackage(model, packageTemporaryPath);
            var validationMessages = ValidatePackage(packageTemporaryPath);
            File.WriteAllText(
                reportTemporaryPath,
                BuildReviewReport(model, validationMessages),
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

            File.Move(packageTemporaryPath, fullPackagePath, overwrite: true);
            File.Move(reportTemporaryPath, reportPath, overwrite: true);
            return new DaisyExportOutcome(fullPackagePath, reportPath, validationMessages);
        }
        finally
        {
            DeleteIfExists(packageTemporaryPath);
            DeleteIfExists(reportTemporaryPath);
        }
    }

    private static DaisyModel CreateModel(OcrDocumentResult result)
    {
        var uid = Guid.TryParse(result.Document.Id, out var documentId)
            ? $"urn:uuid:{documentId:D}"
            : $"urn:uuid:{Guid.NewGuid():D}";
        var title = string.IsNullOrWhiteSpace(result.Document.Title)
            ? "제목 없는 문서"
            : result.Document.Title.Trim();
        var orderedBlocks = result.Blocks
            .OrderBy(block => block.PageNumber)
            .ThenBy(block => block.Y)
            .ThenBy(block => block.X)
            .ToList();
        var pageNumbers = result.Pages
            .Select(page => page.PageIndex + 1)
            .Concat(orderedBlocks.Select(block => block.PageNumber))
            .Where(pageNumber => pageNumber > 0)
            .Distinct()
            .OrderBy(pageNumber => pageNumber)
            .ToList();
        if (pageNumbers.Count == 0)
        {
            pageNumbers.Add(1);
        }

        var sequence = 0;
        var pages = pageNumbers
            .Select(pageNumber =>
            {
                var blocks = orderedBlocks
                    .Where(block => block.PageNumber == pageNumber)
                    .Select(block => new DaisyBlock($"block-{++sequence:00000}", block))
                    .ToList();
                return new DaisyPage(
                    pageNumber,
                    $"page-{pageNumber:0000}",
                    $"smil-page-{pageNumber:0000}",
                    blocks);
            })
            .ToList();
        return new DaisyModel(uid, title, DateTimeOffset.Now, pages);
    }

    private static void WritePackage(DaisyModel model, string path)
    {
        using var stream = new FileStream(path, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create, leaveOpen: false);
        WriteXml(archive, PackageFileName, BuildPackageDocument(model));
        WriteXml(archive, DtbookFileName, BuildDtbookDocument(model));
        WriteXml(archive, NcxFileName, BuildNcxDocument(model));
        WriteXml(archive, SmilFileName, BuildSmilDocument(model));
    }

    private static XDocument BuildPackageDocument(DaisyModel model)
    {
        var metadata = new XElement(
            Package + "metadata",
            new XElement(
                Package + "dc-metadata",
                new XAttribute(XNamespace.Xmlns + "dc", DublinCore),
                new XElement(DublinCore + "Title", model.Title),
                new XElement(
                    DublinCore + "Identifier",
                    new XAttribute("id", "uid"),
                    new XAttribute("scheme", "DTB"),
                    model.Uid),
                new XElement(DublinCore + "Language", "ko"),
                new XElement(DublinCore + "Format", "ANSI/NISO Z39.86-2005"),
                new XElement(DublinCore + "Publisher", "Accessible OCR"),
                new XElement(
                    DublinCore + "Date",
                    new XAttribute("event", "creation"),
                    model.CreatedAt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture))),
            new XElement(
                Package + "x-metadata",
                Meta("dtb:multimediaType", "textNCX"),
                Meta("dtb:multimediaContent", "text"),
                Meta("dtb:totalTime", "00:00:00"),
                Meta("dtb:producedDate", model.CreatedAt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture)),
                Meta("dtb:generator", "Accessible OCR")));

        return XmlDocument(
            new XDocumentType(
                "package",
                "+//ISBN 0-9673008-1-9//DTD OEB 1.2 Package//EN",
                "http://openebook.org/dtds/oeb-1.2/oebpkg12.dtd",
                null),
            new XElement(
                Package + "package",
                new XAttribute("unique-identifier", "uid"),
                new XAttribute("xmlns", Package.NamespaceName),
                metadata,
                new XElement(
                    Package + "manifest",
                    ManifestItem("package", PackageFileName, "text/xml"),
                    ManifestItem("ncx", NcxFileName, "application/x-dtbncx+xml"),
                    ManifestItem("dtbook", DtbookFileName, "application/x-dtbook+xml"),
                    ManifestItem("smil", SmilFileName, "application/smil")),
                new XElement(
                    Package + "spine",
                    new XElement(Package + "itemref", new XAttribute("idref", "smil")))));
    }

    private static XElement Meta(string name, string content)
        => new(
            Package + "meta",
            new XAttribute("name", name),
            new XAttribute("content", content));

    private static XElement ManifestItem(string id, string href, string mediaType)
        => new(
            Package + "item",
            new XAttribute("id", id),
            new XAttribute("href", href),
            new XAttribute("media-type", mediaType));

    private static XDocument BuildDtbookDocument(DaisyModel model)
    {
        var body = new XElement(Dtbook + "bodymatter");
        foreach (var page in model.Pages)
        {
            var level = new XElement(
                Dtbook + "level1",
                new XAttribute("id", $"level-{page.PageNumber:0000}"),
                new XAttribute("class", "print-page"),
                new XElement(Dtbook + "h1", $"{page.PageNumber}페이지"),
                new XElement(
                    Dtbook + "pagenum",
                    new XAttribute("id", page.AnchorId),
                    new XAttribute("page", "normal"),
                    page.PageNumber.ToString(CultureInfo.InvariantCulture)));
            if (page.Blocks.Count == 0)
            {
                level.Add(
                    new XElement(
                        Dtbook + "p",
                        new XAttribute("id", $"empty-{page.PageNumber:0000}"),
                        "인식된 내용이 없습니다."));
            }
            else
            {
                foreach (var block in page.Blocks)
                {
                    level.Add(
                        new XElement(
                            Dtbook + "p",
                            new XAttribute("id", block.Id),
                            new XAttribute("class", BlockClass(block.Source.Type)),
                            DaisyText(block.Source)));
                }
            }

            body.Add(level);
        }

        return XmlDocument(
            new XDocumentType(
                "dtbook",
                "-//NISO//DTD dtbook 2005-3//EN",
                "http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd",
                null),
            new XElement(
                Dtbook + "dtbook",
                new XAttribute("version", "2005-3"),
                new XAttribute(XNamespace.Xml + "lang", "ko"),
                new XElement(
                    Dtbook + "head",
                    DtbookMeta("dtb:uid", model.Uid),
                    DtbookMeta("dc:Title", model.Title),
                    DtbookMeta("dc:Language", "ko"),
                    DtbookMeta("dtb:generator", "Accessible OCR")),
                new XElement(
                    Dtbook + "book",
                    new XElement(
                        Dtbook + "frontmatter",
                        new XElement(Dtbook + "doctitle", model.Title)),
                    body)));
    }

    private static XElement DtbookMeta(string name, string content)
        => new(
            Dtbook + "meta",
            new XAttribute("name", name),
            new XAttribute("content", content));

    private static XDocument BuildNcxDocument(DaisyModel model)
    {
        var navMap = new XElement(Ncx + "navMap");
        var playOrder = 0;
        foreach (var page in model.Pages)
        {
            navMap.Add(
                new XElement(
                    Ncx + "navPoint",
                    new XAttribute("id", $"nav-{page.PageNumber:0000}"),
                    new XAttribute("class", "page"),
                    new XAttribute("playOrder", (++playOrder).ToString(CultureInfo.InvariantCulture)),
                    new XElement(Ncx + "navLabel", new XElement(Ncx + "text", $"{page.PageNumber}페이지")),
                    new XElement(Ncx + "content", new XAttribute("src", $"{SmilFileName}#{page.SmilId}"))));
        }

        return XmlDocument(
            new XDocumentType(
                "ncx",
                "-//NISO//DTD ncx 2005-1//EN",
                "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd",
                null),
            new XElement(
                Ncx + "ncx",
                new XAttribute("version", "2005-1"),
                new XAttribute(XNamespace.Xml + "lang", "ko"),
                new XElement(
                    Ncx + "head",
                    NcxMeta("dtb:uid", model.Uid),
                    NcxMeta("dtb:depth", "1"),
                    NcxMeta("dtb:totalPageCount", model.Pages.Count.ToString(CultureInfo.InvariantCulture)),
                    NcxMeta("dtb:maxPageNumber", model.Pages.Max(page => page.PageNumber).ToString(CultureInfo.InvariantCulture)),
                    NcxMeta("dtb:generator", "Accessible OCR")),
                new XElement(Ncx + "docTitle", new XElement(Ncx + "text", model.Title)),
                navMap));
    }

    private static XElement NcxMeta(string name, string content)
        => new(
            Ncx + "meta",
            new XAttribute("name", name),
            new XAttribute("content", content));

    private static XDocument BuildSmilDocument(DaisyModel model)
    {
        var sequence = new XElement(Smil + "seq", new XAttribute("id", "book-sequence"));
        foreach (var page in model.Pages)
        {
            sequence.Add(
                new XElement(
                    Smil + "par",
                    new XAttribute("id", page.SmilId),
                    new XElement(Smil + "text", new XAttribute("src", $"{DtbookFileName}#{page.AnchorId}"))));
            foreach (var block in page.Blocks)
            {
                sequence.Add(
                    new XElement(
                        Smil + "par",
                        new XAttribute("id", $"smil-{block.Id}"),
                        new XElement(Smil + "text", new XAttribute("src", $"{DtbookFileName}#{block.Id}"))));
            }
        }

        return XmlDocument(
            new XDocumentType(
                "smil",
                "-//NISO//DTD dtbsmil 2005-1//EN",
                "http://www.daisy.org/z3986/2005/dtbsmil-2005-1.dtd",
                null),
            new XElement(
                Smil + "smil",
                new XElement(
                    Smil + "head",
                    new XElement(Smil + "meta", new XAttribute("name", "dtb:uid"), new XAttribute("content", model.Uid)),
                    new XElement(Smil + "meta", new XAttribute("name", "dtb:generator"), new XAttribute("content", "Accessible OCR")),
                    new XElement(Smil + "meta", new XAttribute("name", "dtb:totalElapsedTime"), new XAttribute("content", "00:00:00"))),
                new XElement(Smil + "body", sequence)));
    }

    private static IReadOnlyList<string> ValidatePackage(string path)
    {
        var messages = new List<string>();
        using var archive = ZipFile.OpenRead(path);
        var entries = archive.Entries.ToDictionary(entry => entry.FullName, StringComparer.Ordinal);
        foreach (var required in new[] { PackageFileName, DtbookFileName, NcxFileName, SmilFileName })
        {
            if (!entries.ContainsKey(required))
            {
                throw new InvalidDataException($"DAISY3 필수 파일이 없습니다: {required}");
            }
        }
        messages.Add("필수 파일 4개 확인");

        var package = ReadXml(entries[PackageFileName]);
        var dtbook = ReadXml(entries[DtbookFileName]);
        var ncx = ReadXml(entries[NcxFileName]);
        var smil = ReadXml(entries[SmilFileName]);
        RequireRoot(package, Package + "package", PackageFileName);
        RequireRoot(dtbook, Dtbook + "dtbook", DtbookFileName);
        RequireRoot(ncx, Ncx + "ncx", NcxFileName);
        RequireRoot(smil, Smil + "smil", SmilFileName);
        messages.Add("OPF·DTBook·NCX·SMIL XML 루트 확인");

        var manifestItems = package
            .Descendants(Package + "item")
            .Select(item => (string?)item.Attribute("href"))
            .Where(href => !string.IsNullOrWhiteSpace(href))
            .Cast<string>()
            .ToList();
        foreach (var href in manifestItems)
        {
            if (!entries.ContainsKey(href))
            {
                throw new InvalidDataException($"OPF 매니페스트 파일이 ZIP에 없습니다: {href}");
            }
        }
        if ((string?)package.Descendants(Package + "item").FirstOrDefault(item => (string?)item.Attribute("id") == "ncx")?.Attribute("href") != NcxFileName)
        {
            throw new InvalidDataException("OPF 매니페스트의 ncx 항목이 올바르지 않습니다.");
        }
        messages.Add("OPF 매니페스트 파일 참조 확인");

        var dtbookIds = CollectIds(dtbook, DtbookFileName);
        var smilIds = CollectIds(smil, SmilFileName);
        foreach (var source in smil.Descendants(Smil + "text").Select(element => (string?)element.Attribute("src")))
        {
            ValidateFragmentReference(source, DtbookFileName, dtbookIds, "SMIL→DTBook");
        }
        foreach (var source in ncx.Descendants(Ncx + "content").Select(element => (string?)element.Attribute("src")))
        {
            ValidateFragmentReference(source, SmilFileName, smilIds, "NCX→SMIL");
        }
        messages.Add("NCX→SMIL→DTBook 내부 링크 확인");
        return messages;
    }

    private static HashSet<string> CollectIds(XDocument document, string fileName)
    {
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var id in document.Descendants().Select(element => (string?)element.Attribute("id")).Where(id => !string.IsNullOrWhiteSpace(id)))
        {
            if (!ids.Add(id!))
            {
                throw new InvalidDataException($"{fileName}에 중복 id가 있습니다: {id}");
            }
        }
        return ids;
    }

    private static void ValidateFragmentReference(
        string? source,
        string expectedFile,
        IReadOnlySet<string> availableIds,
        string label)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            throw new InvalidDataException($"{label} 참조가 비어 있습니다.");
        }
        var parts = source.Split('#', 2);
        if (parts.Length != 2 || parts[0] != expectedFile || !availableIds.Contains(parts[1]))
        {
            throw new InvalidDataException($"{label} 참조 대상이 없습니다: {source}");
        }
    }

    private static string BuildReviewReport(
        DaisyModel model,
        IReadOnlyList<string> validationMessages)
    {
        var blocks = model.Pages.SelectMany(page => page.Blocks.Select(block => (page.PageNumber, block.Source))).ToList();
        var needsReview = blocks.Count(item => item.Source.ReviewStatus != ReviewStatus.Reviewed);
        var rows = new StringBuilder();
        foreach (var item in blocks)
        {
            rows.Append("<tr><td>")
                .Append(item.PageNumber)
                .Append("</td><td>")
                .Append(WebUtility.HtmlEncode(item.Source.TypeDisplayName))
                .Append("</td><td>")
                .Append(WebUtility.HtmlEncode(item.Source.Content))
                .Append("</td><td>")
                .Append(WebUtility.HtmlEncode(ReviewStatusText(item.Source.ReviewStatus)))
                .Append("</td><td>")
                .Append(item.Source.Confidence.ToString("P1", CultureInfo.GetCultureInfo("ko-KR")))
                .AppendLine("</td></tr>");
        }
        var checks = string.Join(
            string.Empty,
            validationMessages.Select(message => $"<li>{WebUtility.HtmlEncode(message)}</li>"));
        return $$"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{WebUtility.HtmlEncode(model.Title)}} 검수 보고서</title>
  <style>
    body{font-family:"Malgun Gothic",sans-serif;line-height:1.6;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17212b}
    h1,h2{color:#0c355b} table{border-collapse:collapse;width:100%} caption{text-align:left;font-weight:bold;margin:.5rem 0}
    th,td{border:1px solid #7d8994;padding:.55rem;text-align:left;vertical-align:top} th{background:#eef6ff}
    .warning{padding:1rem;background:#fff8e9;border:1px solid #b05b00}
  </style>
</head>
<body>
  <main>
    <h1>{{WebUtility.HtmlEncode(model.Title)}} 검수 보고서</h1>
    <p>생성 시각: {{model.CreatedAt:yyyy-MM-dd HH:mm:ss zzz}}</p>
    <p>전체 {{blocks.Count}}개 객체 · 검수 필요 또는 미확인 {{needsReview}}개</p>
    <div class="warning">이 보고서는 DAISY 본문과 별도의 검수 기록입니다. 미확인 항목은 원본과 대조하세요.</div>
    <h2>DAISY3 기본 구조 검사</h2>
    <ul>{{checks}}</ul>
    <h2>객체별 검수 상태</h2>
    <table>
      <caption>페이지 순서의 OCR 객체</caption>
      <thead><tr><th scope="col">페이지</th><th scope="col">유형</th><th scope="col">내용</th><th scope="col">상태</th><th scope="col">신뢰도</th></tr></thead>
      <tbody>{{rows}}</tbody>
    </table>
  </main>
</body>
</html>
""";
    }

    private static string DaisyText(ReviewBlock block)
    {
        var content = string.IsNullOrWhiteSpace(block.Content) ? "인식된 내용이 없습니다." : block.Content.Trim();
        var typePrefix = block.Type == BlockType.Text ? string.Empty : $"[{block.TypeDisplayName}] ";
        var statusPrefix = block.ReviewStatus switch
        {
            ReviewStatus.NeedsReview => "[검수 필요] ",
            ReviewStatus.Pending => "[미확인] ",
            _ => string.Empty
        };
        return statusPrefix + typePrefix + content;
    }

    private static string BlockClass(BlockType type) => type switch
    {
        BlockType.Table => "table-description",
        BlockType.Graph => "graph-description",
        BlockType.Math => "math-description",
        BlockType.Music => "music-description",
        BlockType.Image => "image-description",
        _ => "text"
    };

    private static string ReviewStatusText(ReviewStatus status) => status switch
    {
        ReviewStatus.Reviewed => "검수 완료",
        ReviewStatus.NeedsReview => "검수 필요",
        _ => "미확인"
    };

    private static XDocument XmlDocument(XDocumentType documentType, XElement root)
        => new(new XDeclaration("1.0", "UTF-8", null), documentType, root);

    private static void WriteXml(ZipArchive archive, string path, XDocument document)
    {
        var entry = archive.CreateEntry(path, CompressionLevel.Optimal);
        using var stream = entry.Open();
        using var writer = XmlWriter.Create(
            stream,
            new XmlWriterSettings
            {
                Encoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false),
                Indent = true,
                CloseOutput = false
            });
        document.Save(writer);
    }

    private static XDocument ReadXml(ZipArchiveEntry entry)
    {
        using var stream = entry.Open();
        return XDocument.Load(stream, LoadOptions.None);
    }

    private static void RequireRoot(XDocument document, XName expected, string fileName)
    {
        if (document.Root?.Name != expected)
        {
            throw new InvalidDataException($"{fileName} 루트 요소 또는 네임스페이스가 올바르지 않습니다.");
        }
    }

    private static void ValidateDestination(string destinationPath)
    {
        if (string.IsNullOrWhiteSpace(destinationPath))
        {
            throw new ArgumentException("저장 경로가 비어 있습니다.", nameof(destinationPath));
        }
        if (!string.Equals(Path.GetExtension(destinationPath), ".zip", StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException("DAISY3 패키지는 .zip 확장자로 저장해야 합니다.", nameof(destinationPath));
        }
    }

    private static string TemporaryPath(string destinationPath)
    {
        var extension = Path.GetExtension(destinationPath);
        return Path.Combine(
            Path.GetDirectoryName(destinationPath)!,
            $".{Path.GetFileNameWithoutExtension(destinationPath)}.{Guid.NewGuid():N}{extension}");
    }

    private static void DeleteIfExists(string path)
    {
        if (File.Exists(path))
        {
            File.Delete(path);
        }
    }

    private sealed record DaisyModel(
        string Uid,
        string Title,
        DateTimeOffset CreatedAt,
        IReadOnlyList<DaisyPage> Pages);

    private sealed record DaisyPage(
        int PageNumber,
        string AnchorId,
        string SmilId,
        IReadOnlyList<DaisyBlock> Blocks);

    private sealed record DaisyBlock(string Id, ReviewBlock Source);
}
