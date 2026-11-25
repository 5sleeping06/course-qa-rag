package course.qa.model;

/**
 * 一个文本块。vector 为该块的向量表示。
 * charOffset 用于把引用回查到原文位置（验收标准 A3）。
 */
public record Chunk(
        String docId,
        String docName,
        int index,
        int charOffset,
        String text,
        float[] vector) {
}
