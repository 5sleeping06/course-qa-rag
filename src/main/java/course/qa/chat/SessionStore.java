package course.qa.chat;

import course.qa.config.QaProperties;
import course.qa.model.Turn;
import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 会话存储：按 sessionId 保存最近 N 轮问答。
 *
 * 设计取舍：
 * 1. 进程内存储，不引入 Redis——一周项目里会话丢失的代价远低于部署成本；
 * 2. 用 LinkedHashMap 的访问序 + 上限 500 个会话做 LRU 淘汰，避免内存无界增长；
 * 3. 答案只截断保存（默认 300 字），历史只用于消解指代，不需要完整原文。
 */
@Component
public class SessionStore {

    private static final int MAX_SESSIONS = 500;
    private static final int MAX_ANSWER_CHARS = 300;

    private final int maxTurns;
    private final Map<String, Deque<Turn>> sessions = Collections.synchronizedMap(
            new LinkedHashMap<>(64, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, Deque<Turn>> eldest) {
                    return size() > MAX_SESSIONS;
                }
            });

    public SessionStore(QaProperties props) {
        this.maxTurns = Math.max(1, props.getHistoryTurns());
    }

    public void add(String sessionId, String question, String answer) {
        if (sessionId == null || sessionId.isBlank()) {
            return;
        }
        String trimmed = answer == null ? "" : (answer.length() > MAX_ANSWER_CHARS
                ? answer.substring(0, MAX_ANSWER_CHARS) + "…" : answer);
        Deque<Turn> turns = sessions.computeIfAbsent(sessionId, k -> new ArrayDeque<>());
        synchronized (turns) {
            turns.addLast(new Turn(question, trimmed, System.currentTimeMillis()));
            while (turns.size() > maxTurns) {
                turns.removeFirst();
            }
        }
    }

    /** 返回最近 N 轮，按时间从旧到新。 */
    public List<Turn> history(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) {
            return List.of();
        }
        Deque<Turn> turns = sessions.get(sessionId);
        if (turns == null) {
            return List.of();
        }
        synchronized (turns) {
            return new ArrayList<>(turns);
        }
    }

    public int sessionCount() {
        return sessions.size();
    }
}
