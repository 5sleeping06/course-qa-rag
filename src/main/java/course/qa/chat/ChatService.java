package course.qa.chat;

import course.qa.config.QaProperties;
import course.qa.ingest.Embedding;
import course.qa.model.ChatRequest;
import course.qa.model.ChatResponse;
import course.qa.model.Citation;
import course.qa.model.Chunk;
import course.qa.model.Turn;
import course.qa.store.Bm25Index;
import course.qa.store.ScoredChunk;
import course.qa.store.VectorStore;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 问答主流程：改写追问 → 检索 → 阈值判断 → 拼提示词（含历史）→ 流式生成 → 回传引用 → 记录会话。
 */
@Service
public class ChatService {

    private static final Logger log = LoggerFactory.getLogger(ChatService.class);
    /** 拒答话术统一放这里，评测脚本按 status 判断，不依赖措辞。 */
    public static final String REFUSAL_TEXT =
            "资料中没有找到相关内容，我无法回答这个问题。请先上传对应的课程资料，或换一种问法。";

    private final VectorStore store;
    private final Bm25Index bm25;
    private final QaProperties props;
    private final LlmClient llm;
    private final SessionStore sessions;
    private final QueryRewriter rewriter;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public ChatService(VectorStore store, Bm25Index bm25, QaProperties props, LlmClient llm,
                       SessionStore sessions, QueryRewriter rewriter) {
        this.store = store;
        this.bm25 = bm25;
        this.props = props;
        this.llm = llm;
        this.sessions = sessions;
        this.rewriter = rewriter;
        log.info("问答服务就绪：检索={}, 模型={}, 多轮保留 {} 轮",
                props.getRetrievalMode(), llm.name(), props.getHistoryTurns());
    }

    @PreDestroy
    void shutdown() {
        executor.shutdown();
    }

    /**
     * 判定模型是否给出了「资料里没有」的结论。
     *
     * 为什么需要：BM25 在几百块的语料上，对无关问题也会给出 8~14 分，单靠检索阈值无法可靠区分。
     * 只看开头 50 个字：模型常见句式是「先给出资料里的结论，再补充更细的部分没写」，
     * 按全文匹配会把有答案的回答误判成拒答（评测集 E15 暴露过）。
     */
    private static boolean looksRefused(String answer) {
        if (answer == null || answer.isBlank()) {
            return true;
        }
        String compact = answer.replaceAll("\\s+", "");
        // 极短回复视为拒答；阈值不能设高——正确回答可能只有二十几个字（评测集 E08）。
        if (compact.length() < 12) {
            return true;
        }
        String head = compact.substring(0, Math.min(50, compact.length()));
        for (String marker : REFUSAL_MARKERS) {
            if (head.contains(marker)) {
                return true;
            }
        }
        return false;
    }

    private static final String[] REFUSAL_MARKERS = {
            "资料中没有找到", "没有找到相关", "未提及", "未涉及",
            "无法回答", "无法确认", "没有相关内容", "无法据此",
            "无法按", "不能编造", "无法编造", "不能提供", "无法提供"
    };

    // ---------------- 同步接口（供评测脚本） ----------------
    public ChatResponse ask(ChatRequest request) {
        long started = System.currentTimeMillis();
        String question = requireQuestion(request.question());
        String sessionId = resolveSession(request.sessionId());
        int topK = request.topK() != null ? request.topK() : props.getTopK();

        String retrievalQuery = rewriter.rewrite(question, sessionId);
        List<ScoredChunk> hits = retrieve(retrievalQuery, topK);
        if (hits.isEmpty()) {
            return new ChatResponse("refused", REFUSAL_TEXT, List.of(), System.currentTimeMillis() - started);
        }
        List<Chunk> context = hits.stream().map(ScoredChunk::chunk).toList();
        List<Turn> history = sessions.history(sessionId);
        String prompt = PromptBuilder.build(question, context, props.getMaxContextChars(), history);

        StringBuilder answer = new StringBuilder();
        try {
            llm.streamAnswer(new LlmClient.LlmInput(question, context, prompt), answer::append);
        } catch (Exception e) {
            throw new IllegalStateException("生成失败: " + e.getMessage(), e);
        }
        String text = answer.toString();
        if (looksRefused(text)) {
            return new ChatResponse("refused", text, List.of(), System.currentTimeMillis() - started);
        }
        sessions.add(sessionId, question, text);
        return new ChatResponse("answered", text, toCitations(hits), System.currentTimeMillis() - started);
    }

    // ---------------- 流式接口（供前端） ----------------
    public SseEmitter stream(ChatRequest request) {
        SseEmitter emitter = new SseEmitter(300_000L);
        String question;
        try {
            question = requireQuestion(request.question());
        } catch (IllegalArgumentException e) {
            question = null;
        }
        String sessionId = resolveSession(request.sessionId());
        int topK = request.topK() != null ? request.topK() : props.getTopK();
        String finalQuestion = question;
        executor.execute(() -> handleStream(finalQuestion, sessionId, topK, emitter));
        return emitter;
    }

    private void handleStream(String question, String sessionId, int topK, SseEmitter emitter) {
        long started = System.currentTimeMillis();
        try {
            if (question == null) {
                send(emitter, "error", Map.of("code", "INVALID_ARGUMENT", "message", "question 不能为空"));
                emitter.complete();
                return;
            }
            String retrievalQuery = rewriter.rewrite(question, sessionId);
            List<ScoredChunk> hits = retrieve(retrievalQuery, topK);
            send(emitter, "meta", Map.of(
                    "sessionId", sessionId,
                    "retrieved", hits.size(),
                    "mode", llm.name(),
                    "retrieval", props.getRetrievalMode(),
                    "historyTurns", sessions.history(sessionId).size()));

            if (hits.isEmpty()) {
                send(emitter, "delta", Map.of("text", REFUSAL_TEXT));
                send(emitter, "done", Map.of(
                        "status", "refused",
                        "latencyMs", System.currentTimeMillis() - started,
                        "firstTokenMs", System.currentTimeMillis() - started));
                emitter.complete();
                return;
            }

            List<Chunk> context = hits.stream().map(ScoredChunk::chunk).toList();
            List<Turn> history = sessions.history(sessionId);
            String prompt = PromptBuilder.build(question, context, props.getMaxContextChars(), history);
            long[] firstToken = {0L};
            StringBuilder collected = new StringBuilder();

            llm.streamAnswer(new LlmClient.LlmInput(question, context, prompt), piece -> {
                if (firstToken[0] == 0L) {
                    firstToken[0] = System.currentTimeMillis() - started;
                }
                collected.append(piece);
                send(emitter, "delta", Map.of("text", piece));
            });

            boolean refused = looksRefused(collected.toString());
            if (!refused) {
                sessions.add(sessionId, question, collected.toString());
                for (Citation c : toCitations(hits)) {
                    send(emitter, "citation", Map.of(
                            "docId", c.docId(),
                            "docName", c.docName(),
                            "chunkIndex", c.chunkIndex(),
                            "score", c.score(),
                            "snippet", c.snippet()));
                }
            }
            send(emitter, "done", Map.of(
                    "status", refused ? "refused" : "answered",
                    "latencyMs", System.currentTimeMillis() - started,
                    "firstTokenMs", firstToken[0]));
            emitter.complete();
        } catch (Exception e) {
            log.warn("流式问答异常: {}", e.getMessage());
            try {
                send(emitter, "error", Map.of("code", "INTERNAL", "message", String.valueOf(e.getMessage())));
                emitter.complete();
            } catch (Exception ignored) {
                emitter.completeWithError(e);
            }
        }
    }

    private List<ScoredChunk> retrieve(String query, int topK) {
        if ("vector".equalsIgnoreCase(props.getRetrievalMode())) {
            return store.searchVector(Embedding.of(query), topK, props.getMinScore());
        }
        return bm25.search(query, topK, props.getBm25MinScore());
    }

    private List<Citation> toCitations(List<ScoredChunk> hits) {
        List<Citation> list = new ArrayList<>();
        for (ScoredChunk hit : hits) {
            Chunk c = hit.chunk();
            String snippet = c.text().length() > 160 ? c.text().substring(0, 160) + "…" : c.text();
            list.add(new Citation(c.docId(), c.docName(), c.index(), hit.score(), snippet));
        }
        return list;
    }

    private static String requireQuestion(String question) {
        if (question == null || question.isBlank()) {
            throw new IllegalArgumentException("question 不能为空");
        }
        return question.trim();
    }

    private static String resolveSession(String sessionId) {
        return (sessionId == null || sessionId.isBlank())
                ? "s_" + UUID.randomUUID().toString().substring(0, 8)
                : sessionId;
    }

    private static void send(SseEmitter emitter, String event, Object data) throws IOException {
        emitter.send(SseEmitter.event().name(event).data(data, MediaType.APPLICATION_JSON));
    }
}
