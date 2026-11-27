package course.qa.store;

import com.fasterxml.jackson.databind.ObjectMapper;
import course.qa.ingest.Embedding;
import course.qa.model.Chunk;
import course.qa.model.DocumentInfo;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 内存存储 + JSON 落盘。
 *
 * 规模假设：几千个文本块；暴力相似度在毫秒级，不需要引入向量数据库。
 * 索引文件 data/index.json 启动时加载，重启不需重新切块（验收标准 A6）。
 */
@Component
public class VectorStore {

    private static final Logger log = LoggerFactory.getLogger(VectorStore.class);
    private static final int MAX_CHUNKS_PER_DOC = 5000;
    private static final int CANDIDATE_LIMIT = 50;

    private final ObjectMapper mapper;
    private final Path indexFile = Path.of("data", "index.json");
    private final List<Chunk> chunks = new CopyOnWriteArrayList<>();
    private final Map<String, DocumentInfo> documents = new LinkedHashMap<>();
    private final AtomicInteger version = new AtomicInteger(0);

    public VectorStore(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    @PostConstruct
    void load() {
        if (!Files.exists(indexFile)) {
            log.info("索引文件不存在，从空库启动: {}", indexFile.toAbsolutePath());
            return;
        }
        try {
            IndexSnapshot snap = mapper.readValue(Files.readString(indexFile), IndexSnapshot.class);
            if (snap != null) {
                if (snap.chunks() != null) {
                    for (ChunkSnapshot c : snap.chunks()) {
                        chunks.add(new Chunk(c.docId(), c.docName(), c.index(), c.charOffset(), c.text(), c.vector()));
                    }
                }
                if (snap.documents() != null) {
                    for (DocumentInfo d : snap.documents()) {
                        documents.put(d.docId(), d);
                    }
                }
            }
            version.incrementAndGet();
            log.info("索引已加载: {} 篇文档, {} 个文本块", documents.size(), chunks.size());
        } catch (IOException e) {
            log.warn("索引文件读取失败，按空库启动: {}", e.getMessage());
        }
    }

    public DocumentInfo addDocument(String fileName, List<TextSegment> segments) {
        String docId = "d_" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        List<Chunk> newChunks = new ArrayList<>();
        int i = 0;
        long chars = 0;
        for (TextSegment seg : segments) {
            if (i >= MAX_CHUNKS_PER_DOC) {
                break;
            }
            chars += seg.text().length();
            newChunks.add(new Chunk(docId, fileName, i, seg.charOffset(), seg.text(), Embedding.of(seg.text())));
            i++;
        }
        DocumentInfo info = new DocumentInfo(docId, fileName, newChunks.size(), chars,
                LocalDateTime.now().withNano(0).toString());
        synchronized (documents) {
            chunks.addAll(newChunks);
            documents.put(docId, info);
            persist();
            version.incrementAndGet();
        }
        log.info("入库完成: {} docId={} 块数={}", fileName, docId, newChunks.size());
        return info;
    }

    /**
     * 向量检索：块级余弦粗排 → 候选取「句级最大相似度」精排。
     * 短问题与长段落直接算余弦时，分母含大量无关字词，得分偏低会被误判为「资料缺失」，
     * 句级重排能显著缓解这个问题。
     */
    public List<ScoredChunk> searchVector(float[] queryVector, int topK, double minScore) {
        List<ScoredChunk> coarse = chunks.stream()
                .map(c -> new ScoredChunk(c, Embedding.cosine(queryVector, c.vector())))
                .sorted(Comparator.comparingDouble(ScoredChunk::score).reversed())
                .limit(CANDIDATE_LIMIT)
                .toList();
        return coarse.stream()
                .map(s -> new ScoredChunk(s.chunk(), Math.max(s.score(), bestSentenceScore(queryVector, s.chunk().text()))))
                .filter(s -> s.score() >= minScore)
                .sorted(Comparator.comparingDouble(ScoredChunk::score).reversed())
                .limit(Math.max(1, topK))
                .toList();
    }

    private static double bestSentenceScore(float[] queryVector, String text) {
        double best = 0.0;
        for (String sentence : text.split("[。！？!?\\n]")) {
            String s = sentence.trim();
            if (s.length() < 6) {
                continue;
            }
            best = Math.max(best, Embedding.cosine(queryVector, Embedding.of(s)));
        }
        return best;
    }

    /** 按文档与块序号取块，供邻块扩展使用。 */
    public Chunk findChunk(String docId, int index) {
        for (Chunk c : chunks) {
            if (c.index() == index && c.docId().equals(docId)) {
                return c;
            }
        }
        return null;
    }

    public List<Chunk> snapshotChunks() {
        return List.copyOf(chunks);
    }

    public int version() {
        return version.get();
    }

    public List<DocumentInfo> listDocuments() {
        synchronized (documents) {
            return new ArrayList<>(documents.values());
        }
    }

    public boolean removeDocument(String docId) {
        synchronized (documents) {
            boolean removed = documents.remove(docId) != null;
            if (removed) {
                chunks.removeIf(c -> c.docId().equals(docId));
                persist();
                version.incrementAndGet();
            }
            return removed;
        }
    }

    public int chunkCount() {
        return chunks.size();
    }

    private void persist() {
        try {
            Files.createDirectories(indexFile.getParent());
            IndexSnapshot snap = new IndexSnapshot(
                    new ArrayList<>(documents.values()),
                    chunks.stream()
                            .map(c -> new ChunkSnapshot(c.docId(), c.docName(), c.index(), c.charOffset(), c.text(), c.vector()))
                            .toList());
            mapper.writeValue(indexFile.toFile(), snap);
        } catch (IOException e) {
            log.error("索引落盘失败: {}", e.getMessage());
        }
    }

    public record TextSegment(int charOffset, String text) {
    }

    public record IndexSnapshot(List<DocumentInfo> documents, List<ChunkSnapshot> chunks) {
    }

    public record ChunkSnapshot(String docId, String docName, int index, int charOffset, String text, float[] vector) {
    }
}
