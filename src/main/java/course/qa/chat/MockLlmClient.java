package course.qa.chat;

import course.qa.model.Chunk;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 离线抽取式回答（mock）。不调用任何外部服务：把检索到的最相关片段组织成答案并逐字流出。
 *
 * 用途：
 *  1) 没有 API Key 也能跑通端到端链路，便于单测与演示（答辩现场不怕断网）；
 *  2) 作为「无模型」对照组，报告里可以对比「检索本身够不够用」。
 */
@Component
@ConditionalOnProperty(name = "qa.llm-mode", havingValue = "mock", matchIfMissing = true)
public class MockLlmClient implements LlmClient {

    @Override
    public String name() {
        return "mock";
    }

    @Override
    public void streamAnswer(LlmInput input, DeltaConsumer onDelta) throws Exception {
        List<Chunk> ctx = input.context();
        StringBuilder sb = new StringBuilder();
        if (ctx.isEmpty()) {
            sb.append("资料中没有找到相关内容。");
        } else {
            sb.append("根据课程资料，");
            Chunk top = ctx.get(0);
            sb.append(top.text().length() > 160 ? top.text().substring(0, 160) + "…" : top.text());
            if (ctx.size() > 1) {
                sb.append("（另见第 2 条引用的补充说明）");
            }
            sb.append(" 以上内容摘自《").append(top.docName()).append("》第 ").append(top.index()).append(" 块。");
        }
        String answer = sb.toString();
        for (int i = 0; i < answer.length(); i += 4) {
            int end = Math.min(answer.length(), i + 4);
            onDelta.accept(answer.substring(i, end));
            Thread.sleep(12);
        }
    }

    /** 离线模式没有改写能力，返回空串，让 QueryRewriter 退回「上一问 + 当前问」拼接。 */
    @Override
    public String complete(String prompt) {
        return "";
    }
}
