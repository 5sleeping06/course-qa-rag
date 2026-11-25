package course.qa.model;

/** 一轮对话：用户问 + 助手答（答案截断后存，避免会话内存无限增长）。 */
public record Turn(String question, String answer, long timestamp) {
}
