package course.qa.model;

/**
 * 问答请求。topK 为空时使用配置值。
 */
public record ChatRequest(String question, String sessionId, Integer topK) {
}
