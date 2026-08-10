using System.IO.Compression;
using System.IO;
using System.Text.Json;
using System.Xml.Linq;
using AccessibleOcr.Desktop.Models;

namespace AccessibleOcr.Desktop.Services;

public sealed class OcrPackageReader
{
    public async Task<OcrDocumentResult> ReadAsync(Stream packageStream, string sourceFileName, CancellationToken cancellationToken = default)
    {
        using var archive = new ZipArchive(packageStream, ZipArchiveMode.Read, leaveOpen: false);
        var bookEntry = archive.Entries.FirstOrDefault(entry => entry.FullName.EndsWith("book.xml", StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidDataException("결과 패키지에 book.xml이 없습니다.");
        var reviewEntry = archive.Entries.FirstOrDefault(entry => entry.FullName.EndsWith("review.json", StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidDataException("결과 패키지에 review.json이 없습니다.");

        XDocument book;
        await using (var bookStream = bookEntry.Open())
        {
            book = await XDocument.LoadAsync(bookStream, LoadOptions.None, cancellationToken);
        }

        JsonDocument review;
        await using (var reviewStream = reviewEntry.Open())
        {
            review = await JsonDocument.ParseAsync(reviewStream, cancellationToken: cancellationToken);
        }

        using (review)
        {
            var root = review.RootElement;
            var documentId = GetString(root, "document_id") ?? Guid.NewGuid().ToString("N");
            var pages = ParsePages(root);
            var textByElementId = ParseDtBookText(book);
            var blocks = ParseReviewElements(root, pages, textByElementId);
            var summary = new DocumentSummary(documentId, sourceFileName, DocumentStatus.AiDraft, DateTimeOffset.Now);

            return new OcrDocumentResult(summary, pages, blocks);
        }
    }

    private static IReadOnlyList<OcrPage> ParsePages(JsonElement root)
    {
        var pages = new List<OcrPage>();
        if (!root.TryGetProperty("pages", out var pageArray) || pageArray.ValueKind != JsonValueKind.Array)
        {
            return pages;
        }

        foreach (var page in pageArray.EnumerateArray())
        {
            pages.Add(new OcrPage(
                GetInt(page, "page_index"),
                GetInt(page, "width"),
                GetInt(page, "height"),
                GetInt(page, "dpi", 300)));
        }

        return pages;
    }

    private static Dictionary<string, string> ParseDtBookText(XDocument book)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var element in book.Descendants().Where(element => element.Attribute("id") is not null))
        {
            var id = element.Attribute("id")!.Value;
            var altText = element.Descendants().Attributes("alttext").Select(attribute => attribute.Value).FirstOrDefault();
            var text = string.Join(" ", element.DescendantNodes().OfType<XText>().Select(textNode => textNode.Value.Trim()).Where(text => text.Length > 0));
            result[id] = string.IsNullOrWhiteSpace(text) ? altText ?? string.Empty : text;
        }

        return result;
    }

    private static IReadOnlyList<ReviewBlock> ParseReviewElements(JsonElement root, IReadOnlyList<OcrPage> pages, IReadOnlyDictionary<string, string> textByElementId)
    {
        var blocks = new List<ReviewBlock>();
        if (!root.TryGetProperty("elements", out var elements) || elements.ValueKind != JsonValueKind.Object)
        {
            return blocks;
        }

        foreach (var property in elements.EnumerateObject())
        {
            var data = property.Value;
            var pageIndex = GetInt(data, "page_index");
            var page = pages.FirstOrDefault(item => item.PageIndex == pageIndex) ?? new OcrPage(pageIndex, 1, 1, 300);
            var bbox = data.TryGetProperty("bbox", out var rawBbox) && rawBbox.ValueKind == JsonValueKind.Array
                ? rawBbox.EnumerateArray().Select(value => value.GetDouble()).ToArray()
                : new double[] { 0, 0, 0, 0 };
            var confidence = data.TryGetProperty("confidence", out var confidenceValue) ? confidenceValue.GetDouble() : 0;

            blocks.Add(new ReviewBlock
            {
                Id = property.Name,
                PageNumber = pageIndex + 1,
                PageWidth = page.Width,
                PageHeight = page.Height,
                Type = ParseBlockType(GetString(data, "type")),
                Confidence = confidence,
                X = bbox.ElementAtOrDefault(0),
                Y = bbox.ElementAtOrDefault(1),
                Width = bbox.ElementAtOrDefault(2),
                Height = bbox.ElementAtOrDefault(3),
                Content = textByElementId.TryGetValue(property.Name, out var text) ? text : string.Empty,
                RegionReference = GetString(data, "region_ref"),
                ReviewStatus = confidence < 0.8 ? ReviewStatus.NeedsReview : ReviewStatus.Pending
            });
        }

        return blocks.OrderBy(block => block.PageNumber).ThenBy(block => block.Y).ToArray();
    }

    private static BlockType ParseBlockType(string? value) => value?.ToLowerInvariant() switch
    {
        "table" => BlockType.Table,
        "graph" => BlockType.Graph,
        "formula" or "math" => BlockType.Math,
        "music" => BlockType.Music,
        "image" => BlockType.Image,
        _ => BlockType.Text
    };

    private static int GetInt(JsonElement element, string propertyName, int defaultValue = 0)
        => element.TryGetProperty(propertyName, out var value) && value.TryGetInt32(out var result) ? result : defaultValue;

    private static string? GetString(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var value) ? value.GetString() : null;
}
