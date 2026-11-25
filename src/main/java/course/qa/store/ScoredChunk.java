package course.qa.store;

import course.qa.model.Chunk;

/** 检索结果：块 + 得分（向量模式为余弦，BM25 模式为原始 BM25 分）。 */
public record ScoredChunk(Chunk chunk, double score) {
}
