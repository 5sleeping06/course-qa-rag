package course.qa.ingest;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFTable;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * 文档解析：.txt / .md / .pdf / .docx → 纯文本。
 *
 * 编码策略：中文课件常见 UTF-8(BOM)、UTF-8、GB18030 三种，
 * 依次严格解码，全部失败才报错——不做「猜编码后静默乱码」这种更糟的处理。
 */
public final class DocumentParser {

    private DocumentParser() {
    }

    public static String extract(String fileName, byte[] bytes) throws IOException {
        String lower = fileName.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".pdf")) {
            return fromPdf(bytes);
        }
        if (lower.endsWith(".docx")) {
            return fromDocx(bytes);
        }
        if (lower.endsWith(".doc")) {
            throw new IllegalArgumentException("暂不支持旧版 .doc，请另存为 .docx 后上传");
        }
        if (lower.endsWith(".txt") || lower.endsWith(".md")) {
            return decode(bytes);
        }
        throw new IllegalArgumentException("不支持的文件类型: " + fileName + "（支持 .txt/.md/.pdf/.docx）");
    }

    private static String decode(byte[] bytes) {
        for (Charset cs : new Charset[]{StandardCharsets.UTF_8, Charset.forName("GB18030")}) {
            try {
                String text = cs.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(bytes))
                        .toString();
                return stripBom(text);
            } catch (CharacterCodingException ignored) {
                // 试下一种编码
            }
        }
        throw new IllegalArgumentException("无法识别文件编码（已尝试 UTF-8 与 GB18030）");
    }

    private static String stripBom(String text) {
        return text.startsWith("\uFEFF") ? text.substring(1) : text;
    }

    private static String fromPdf(byte[] bytes) throws IOException {
        try (PDDocument doc = PDDocument.load(bytes)) {
            if (doc.isEncrypted()) {
                throw new IllegalArgumentException("PDF 已加密，无法解析");
            }
            if (doc.getNumberOfPages() == 0) {
                throw new IllegalArgumentException("PDF 没有页面");
            }
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            String text = stripper.getText(doc);
            if (text == null || text.isBlank()) {
                throw new IllegalArgumentException("PDF 没有可提取的文本层（可能是扫描版，需 OCR）");
            }
            return normalize(text);
        }
    }

    private static String fromDocx(byte[] bytes) throws IOException {
        try (XWPFDocument doc = new XWPFDocument(new ByteArrayInputStream(bytes))) {
            StringBuilder sb = new StringBuilder();
            for (XWPFParagraph p : doc.getParagraphs()) {
                String t = p.getText();
                if (t != null && !t.isBlank()) {
                    sb.append(t).append('\n');
                }
            }
            for (XWPFTable table : doc.getTables()) {
                table.getRows().forEach(row -> row.getTableCells().forEach(cell -> {
                    String t = cell.getText();
                    if (t != null && !t.isBlank()) {
                        sb.append(t).append('\n');
                    }
                }));
            }
            if (sb.length() == 0) {
                throw new IllegalArgumentException("DOCX 中没有可提取的文本");
            }
            return normalize(sb.toString());
        }
    }

    /** 折叠 3 个以上连续换行，去掉行尾空白。 */
    private static String normalize(String text) {
        return text.replace("\r\n", "\n")
                .replace('\r', '\n')
                .replaceAll("[ \t]+\n", "\n")
                .replaceAll("\n{3,}", "\n\n")
                .trim();
    }
}
