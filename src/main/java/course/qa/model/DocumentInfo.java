package course.qa.model;

/**
 * 已入库文档的元信息。
 */
public record DocumentInfo(
        String docId,
        String fileName,
        int chunks,
        long chars,
        String createdAt) {
}
