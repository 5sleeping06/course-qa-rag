package course.qa.web;

import course.qa.config.QaProperties;
import course.qa.ingest.DocumentParser;
import course.qa.ingest.TextChunker;
import course.qa.model.DocumentInfo;
import course.qa.store.VectorStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {

    private static final Logger log = LoggerFactory.getLogger(DocumentController.class);

    private final VectorStore store;
    private final QaProperties props;

    public DocumentController(VectorStore store, QaProperties props) {
        this.store = store;
        this.props = props;
    }

    @GetMapping
    public Map<String, Object> list() {
        List<DocumentInfo> docs = store.listDocuments();
        return Map.of("total", docs.size(), "chunkCount", store.chunkCount(), "documents", docs);
    }

    @PostMapping
    public ResponseEntity<?> upload(@RequestParam("file") MultipartFile file) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("文件为空");
        }
        String name = file.getOriginalFilename() == null ? "unnamed" : file.getOriginalFilename();
        if (name.contains("/") || name.contains("\\")) {
            throw new IllegalArgumentException("文件名非法: " + name);
        }
        long t0 = System.currentTimeMillis();
        String text = DocumentParser.extract(name, file.getBytes());
        List<TextChunker.Segment> segments = TextChunker.chunk(text, props.getChunkSize(), props.getChunkOverlap());
        if (segments.isEmpty()) {
            throw new IllegalArgumentException("解析后没有有效文本");
        }
        DocumentInfo info = store.addDocument(name, segments.stream()
                .map(s -> new VectorStore.TextSegment(s.charOffset(), s.text()))
                .toList());
        log.info("上传完成: {} -> {} 块, 耗时 {}ms", name, info.chunks(), System.currentTimeMillis() - t0);
        return ResponseEntity.status(HttpStatus.CREATED).body(info);
    }

    @DeleteMapping("/{docId}")
    public Map<String, Object> delete(@PathVariable String docId) {
        if (!store.removeDocument(docId)) {
            throw new NotFoundException("文档不存在: " + docId);
        }
        return Map.of("deleted", docId);
    }

    public static class NotFoundException extends RuntimeException {
        public NotFoundException(String message) {
            super(message);
        }
    }
}
