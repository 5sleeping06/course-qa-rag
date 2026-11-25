package course.qa.model;

import java.util.List;

/**
 * 同步问答响应（供评测脚本打分，必须是纯 JSON）。
 * status 只有两个取值：answered / refused。
 */
public record ChatResponse(
        String status,
        String answer,
        List<Citation> citations,
        long latencyMs) {
}
