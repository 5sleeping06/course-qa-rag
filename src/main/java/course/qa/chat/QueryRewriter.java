package course.qa.chat;

import course.qa.model.Turn;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.regex.Pattern;

/**
 * 追问改写：把「它一般等多久」这类依赖上下文的问题，改写成可以独立检索的查询。
 *
 * 为什么需要：检索器只看到一个孤立的问句时，代词和省略会让 BM25 完全抓不到主题。
 * 第一轮问「碳交易市场的数据来源」，第二轮问「这些数据怎么用」——
 * 若不改写，检索查询里没有任何关键词，命中率会骤降。
 *
 * 策略（成本由低到高）：
 *   1. 不像追问（够长、无指代词）→ 原样返回，不额外调用模型；
 *   2. 像追问 → 让模型用历史改写成一句独立查询；
 *   3. 模型失败或输出不合理 → 退化为「上一问 + 当前问」拼接，保证不至于空查询。
 */
@Component
public class QueryRewriter {

    private static final Logger log = LoggerFactory.getLogger(QueryRewriter.class);
    private static final Pattern ANAPHORA = Pattern.compile("它|他们|她们|它们|这个|那个|这些|那些|该|此|上面|刚才|前面|其中|后者|前者");
    private static final int SHORT_QUESTION_CHARS = 12;

    private final LlmClient llm;
    private final SessionStore sessions;

    public QueryRewriter(LlmClient llm, SessionStore sessions) {
        this.llm = llm;
        this.sessions = sessions;
    }

    public String rewrite(String question, String sessionId) {
        List<Turn> history = sessions.history(sessionId);
        if (history.isEmpty() || !looksLikeFollowUp(question)) {
            return question;
        }
        String prompt = buildPrompt(question, history);
        try {
            String out = llm.complete(prompt);
            if (out != null) {
                String cleaned = out.replaceAll("[\\r\\n]+", " ").trim();
                if (cleaned.length() >= 2 && cleaned.length() <= 60) {
                    log.info("追问改写: {} -> {}", question, cleaned);
                    return cleaned;
                }
            }
        } catch (Exception e) {
            log.warn("追问改写失败，退化为拼接: {}", e.getMessage());
        }
        Turn last = history.get(history.size() - 1);
        return last.question() + " " + question;
    }

    private boolean looksLikeFollowUp(String question) {
        if (question == null) {
            return false;
        }
        String q = question.trim();
        return q.length() <= SHORT_QUESTION_CHARS || ANAPHORA.matcher(q).find();
    }

    private String buildPrompt(String question, List<Turn> history) {
        StringBuilder sb = new StringBuilder("以下是学生与助教的历史对话：\n");
        for (Turn t : history) {
            sb.append("学生：").append(t.question()).append('\n');
            String ans = t.answer();
            sb.append("助教：").append(ans.length() > 120 ? ans.substring(0, 120) + "…" : ans).append('\n');
        }
        sb.append("\n学生的新问题：").append(question).append('\n');
        sb.append("""
                
                请把新问题改写成一个**可以脱离上下文独立检索**的完整问句：
                - 把「它」「这些」「刚才说的」等指代替换成具体名词；
                - 保留原问题的疑问点，不要回答问题；
                - 只输出改写后的问句一行，不要解释、不要引号。
                """);
        return sb.toString();
    }
}
