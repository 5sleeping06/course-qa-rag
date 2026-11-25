package course.qa.ingest;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 面向中文的轻量分词器：CJK 连续段切成字符二元组，拉丁字母与数字切成单词。
 *
 * 为什么不用 IKAnalyzer / jieba：本项目的查询是专业术语短句，二元组足够召回，
 * 且不引入词典与额外依赖；报告里可作为「检索粒度」的对比实验（1-gram / 2-gram）。
 */
public final class Tokenizer {

    private Tokenizer() {
    }

    public static List<String> tokenize(String text) {
        List<String> tokens = new ArrayList<>();
        if (text == null || text.isEmpty()) {
            return tokens;
        }
        String s = text.toLowerCase(Locale.ROOT);
        StringBuilder latin = new StringBuilder();
        StringBuilder cjk = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (isCjk(ch)) {
                flushLatin(latin, tokens);
                cjk.append(ch);
            } else if (Character.isLetterOrDigit(ch)) {
                flushCjk(cjk, tokens);
                latin.append(ch);
            } else {
                flushLatin(latin, tokens);
                flushCjk(cjk, tokens);
            }
        }
        flushLatin(latin, tokens);
        flushCjk(cjk, tokens);
        return tokens;
    }

    private static void flushLatin(StringBuilder buf, List<String> out) {
        if (buf.length() > 0) {
            out.add(buf.toString());
            buf.setLength(0);
        }
    }

    private static void flushCjk(StringBuilder buf, List<String> out) {
        int n = buf.length();
        if (n == 0) {
            return;
        }
        if (n == 1) {
            out.add(buf.toString());
        } else {
            for (int i = 0; i + 1 < n; i++) {
                out.add(buf.substring(i, i + 2));
            }
        }
        buf.setLength(0);
    }

    private static boolean isCjk(char ch) {
        return ch >= 0x4E00 && ch <= 0x9FFF;
    }
}
