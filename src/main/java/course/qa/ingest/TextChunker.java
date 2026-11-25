package course.qa.ingest;

import java.util.ArrayList;
import java.util.List;

/**
 * 定长滑窗切块：size 个字，相邻块重叠 overlap 个字。
 * 保留每块的字符偏移，供引用回查。
 */
public final class TextChunker {

    private TextChunker() {
    }

    public static List<Segment> chunk(String text, int size, int overlap) {
        List<Segment> result = new ArrayList<>();
        if (text == null) {
            return result;
        }
        String normalized = text.replace("\r\n", "\n").replace('\r', '\n').trim();
        if (normalized.isEmpty()) {
            return result;
        }
        int step = Math.max(1, size - overlap);
        for (int start = 0; start < normalized.length(); start += step) {
            int end = Math.min(normalized.length(), start + size);
            String piece = normalized.substring(start, end).trim();
            if (!piece.isEmpty()) {
                result.add(new Segment(start, piece));
            }
            if (end >= normalized.length()) {
                break;
            }
        }
        return result;
    }

    public record Segment(int charOffset, String text) {
    }
}
