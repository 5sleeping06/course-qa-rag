package course.qa.model;

/**
 * 回答中的引用。snippet 必须是原文片段，可回查（验收标准 A3）。
 */
public record Citation(
        String docId,
        String docName,
        int chunkIndex,
        double score,
        String snippet) {
}
