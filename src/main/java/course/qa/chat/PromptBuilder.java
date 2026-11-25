package course.qa.chat;

import course.qa.model.Chunk;
import course.qa.model.Turn;

import java.util.List;

/**
 * 提示词组装：控制上下文预算，并要求模型用 [编号] 标注来源（便于服务端映射回真实块）。
 * 多轮场景下额外注入最近的问答历史，供模型理解指代。
 */
public final class PromptBuilder {

    private static final int HISTORY_ANSWER_CHARS = 120;

    private PromptBuilder() {
    }

    public static String build(String question, List<Chunk> chunks, int maxContextChars) {
        return build(question, chunks, maxContextChars, List.of());
    }

    public static String build(String question, List<Chunk> chunks, int maxContextChars, List<Turn> history) {
        StringBuilder ctx = new StringBuilder();
        int no = 1;
        for (Chunk c : chunks) {
            String block = "[" + no + "] 《" + c.docName() + "》第 " + c.index() + " 块：\n" + c.text() + "\n\n";
            if (ctx.length() + block.length() > maxContextChars) {
                break;
            }
            ctx.append(block);
            no++;
        }

        StringBuilder sb = new StringBuilder();
        if (history != null && !history.isEmpty()) {
            sb.append("历史对话（仅用于理解指代，结论仍须来自资料）：\n");
            for (Turn t : history) {
                String ans = t.answer() == null ? "" : t.answer();
                if (ans.length() > HISTORY_ANSWER_CHARS) {
                    ans = ans.substring(0, HISTORY_ANSWER_CHARS) + "…";
                }
                sb.append("学生：").append(t.question()).append('\n');
                sb.append("助教：").append(ans.replace("\n", " ")).append('\n');
            }
            sb.append('\n');
        }
        sb.append("资料：\n").append(ctx);
        sb.append("\n问题：").append(question).append('\n');
        sb.append("\n请只依据上面的资料回答；资料不足就直说，不要编造。结论后请用 [编号] 标注来源。");
        return sb.toString();
    }
}
