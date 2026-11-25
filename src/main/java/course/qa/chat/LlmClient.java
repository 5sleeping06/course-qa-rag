package course.qa.chat;

import course.qa.model.Chunk;

import java.util.List;

/**
 * 大模型客户端抽象。两种实现：
 *   MockLlmClient      —— 离线抽取式回答，不需要 Key，用于冒烟与演示兜底
 *   OpenAiLlmClient    —— OpenAI 兼容接口（DeepSeek / 通义 / Kimi / Ollama）
 */
public interface LlmClient {

    String name();

    /** 流式生成回答，每产生一段文本就回调一次 onDelta。 */
    void streamAnswer(LlmInput input, DeltaConsumer onDelta) throws Exception;

    /** 一次性生成（用于追问改写这类短任务）。 */
    String complete(String prompt) throws Exception;

    record LlmInput(String question, List<Chunk> context, String prompt) {
    }

    @FunctionalInterface
    interface DeltaConsumer {
        void accept(String delta) throws Exception;
    }
}
