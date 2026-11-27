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

    /** 同一行重复超过该次数，视为模板（页眉/导航条）。 */
    private static final int REPEAT_THRESHOLD = 3;
    private static final int REPEAT_MAX_LEN = 60;
    private static final String[] FIXED_NOISE = {"China University of Mining"};

    private DocumentParser() {
    }

    public static String extract(String fileName, byte[] bytes) throws IOException {
        String lower = fileName.toLowerCase(Locale.ROOT);
        String raw;
        if (lower.endsWith(".pdf")) {
            raw = fromPdf(bytes);
        } else if (lower.endsWith(".docx")) {
            raw = fromDocx(bytes);
        } else if (lower.endsWith(".doc")) {
            throw new IllegalArgumentException("暂不支持旧版 .doc，请另存为 .docx 后上传");
        } else if (lower.endsWith(".txt") || lower.endsWith(".md")) {
            raw = decode(bytes);
        } else {
            throw new IllegalArgumentException("不支持的文件类型: " + fileName + "（支持 .txt/.md/.pdf/.docx）");
        }
        return stripBoilerplate(raw);
    }

    /**
     * 去掉 PPT 转文本时反复出现的页眉/导航条。
     *
     * 为什么必须做：课件每页都带着「中国矿业大学 / 第二章能源大数据关键技术与管理应用 / 2.1…2.6」
     * 这类模板行，它们恰好包含「能源大数据」「关键技术」，会让检索把它们当成高相关内容，
     * 实测中封面块一度排到第 2 位、真正讲采集/存储/分析的块被挤掉。
     * 判定规则：同一行在同一文档中出现 ≥3 次且长度 ≤60 字，视为模板行。
     */
    private static String stripBoilerplate(String text) {
        String[] lines = text.split("\n", -1);
        java.util.Map<String, Integer> freq = new java.util.HashMap<>();
        for (String line : lines) {
            String key = line.trim();
            if (!key.isEmpty() && key.length() <= REPEAT_MAX_LEN) {
                freq.merge(key, 1, Integer::sum);
            }
        }
        StringBuilder sb = new StringBuilder(text.length());
        for (String line : lines) {
            String key = line.trim();
            if (isFixedNoise(key)) {
                continue;
            }
            if (!key.isEmpty() && key.length() <= REPEAT_MAX_LEN
                    && freq.getOrDefault(key, 0) >= REPEAT_THRESHOLD) {
                continue;
            }
            sb.append(line).append('\n');
        }
        return sb.toString().replaceAll("\n{3,}", "\n\n").trim();
    }

    private static boolean isFixedNoise(String line) {
        if (line.isEmpty()) {
            return false;
        }
        for (String noise : FIXED_NOISE) {
            if (line.contains(noise)) {
                return true;
            }
        }
        return false;
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
