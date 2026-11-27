package course.qa.store;

import course.qa.ingest.Tokenizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * BM25 词法检索。
 *
 * 为什么是 BM25 而不是向量检索：DeepSeek 未提供 embedding 接口（/embeddings 返回 404），
 * 而本项目又不希望为了向量化再引入第二个供应商与密钥。BM25 在「专业术语、课件原文」
 * 这类场景召回到位，且完全离线、可解释、可复现——适合作为课程项目的主检索器。
 * 向量检索保留为可选模式（qa.retrieval-mode=vector），接入任意 OpenAI 兼容 embedding 即可切换。
 *
 * 索引按需构建，用 store 的版本号做失效判断，避免每次入库都全量重算。
 */
@Component
public class Bm25Index {

    private static final Logger log = LoggerFactory.getLogger(Bm25Index.class);
    private static final double K1 = 1.2;
    private static final double B = 0.75;

    private final VectorStore store;

    private volatile int builtVersion = -1;
    private volatile List<Entry> entries = List.of();
    private volatile Map<String, Integer> docFreq = Map.of();
    private volatile double avgLength = 1.0;

    public Bm25Index(VectorStore store) {
        this.store = store;
    }

    public List<ScoredChunk> search(String question, int topK, double minScore) {
        ensureBuilt();
        List<String> queryTokens = Tokenizer.tokenize(question);
        if (queryTokens.isEmpty()) {
            return List.of();
        }
        Map<String, Integer> queryTf = new HashMap<>();
        for (String t : queryTokens) {
            queryTf.merge(t, 1, Integer::sum);
        }

        int total = entries.size();
        Map<String, Double> docBoost = docTitleBoost(queryTf.keySet());
        List<ScoredChunk> scored = new ArrayList<>();
        for (Entry e : entries) {
            double score = 0.0;
            for (Map.Entry<String, Integer> q : queryTf.entrySet()) {
                Integer tf = e.tf().get(q.getKey());
                if (tf == null) {
                    continue;
                }
                int df = docFreq.getOrDefault(q.getKey(), 1);
                double idf = Math.log(1.0 + (total - df + 0.5) / (df + 0.5));
                double denom = tf + K1 * (1 - B + B * e.length() / avgLength);
                score += idf * (tf * (K1 + 1)) / denom;
            }
            score *= docBoost.getOrDefault(e.chunk().docName(), 1.0);
            if (score > 0 && score >= minScore) {
                scored.add(new ScoredChunk(e.chunk(), Math.round(score * 1000) / 1000.0));
            }
        }
        return scored.stream()
                .sorted(Comparator.comparingDouble(ScoredChunk::score).reversed())
                .limit(Math.max(1, topK))
                .toList();
    }

    /**
     * 文档标题加权：问题与文件名重合度越高，该文档的块越优先。
     *
     * 为什么需要：语料里有两份课件都讲「关键技术」，一份是《第二章 能源大数据关键技术与管理应用》，
     * 一份是《企业能源大数据管理》。问「能源大数据的关键技术」时，前者显然更对，但 BM25 只看块内词频，
     * 分不出这个差别。这里用文件名与查询的词重合度做一个温和的放大（最多 +35%）。
     */
    private Map<String, Double> docTitleBoost(Set<String> queryTokens) {
        Map<String, Double> boost = new HashMap<>();
        if (queryTokens.isEmpty()) {
            return boost;
        }
        for (Entry e : entries) {
            String docName = e.chunk().docName();
            if (boost.containsKey(docName)) {
                continue;
            }
            Set<String> titleTokens = new HashSet<>(Tokenizer.tokenize(docName));
            int hit = 0;
            for (String q : queryTokens) {
                if (titleTokens.contains(q)) {
                    hit++;
                }
            }
            double ratio = (double) hit / queryTokens.size();
            boost.put(docName, 1.0 + 0.35 * ratio);
        }
        return boost;
    }

    private void ensureBuilt() {
        int current = store.version();
        if (current == builtVersion) {
            return;
        }
        synchronized (this) {
            if (current == builtVersion) {
                return;
            }
            List<course.qa.model.Chunk> chunks = store.snapshotChunks();
            Map<String, Integer> df = new HashMap<>();
            List<Entry> built = new ArrayList<>(chunks.size());
            long totalLen = 0;
            for (course.qa.model.Chunk c : chunks) {
                Map<String, Integer> tf = new HashMap<>();
                int len = 0;
                for (String token : Tokenizer.tokenize(c.text())) {
                    tf.merge(token, 1, Integer::sum);
                    len++;
                }
                tf.keySet().forEach(t -> df.merge(t, 1, Integer::sum));
                built.add(new Entry(c, tf, Math.max(len, 1)));
                totalLen += Math.max(len, 1);
            }
            entries = built;
            docFreq = df;
            avgLength = built.isEmpty() ? 1.0 : (double) totalLen / built.size();
            builtVersion = current;
            log.info("BM25 索引重建: {} 块, 词表 {} 项, 平均长度 {}",
                    built.size(), df.size(), Math.round(avgLength));
        }
    }

    private record Entry(course.qa.model.Chunk chunk, Map<String, Integer> tf, int length) {
    }
}
