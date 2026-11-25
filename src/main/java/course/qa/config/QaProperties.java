package course.qa.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 全部关键参数集中在这里，便于报告中做「参数扫描」实验。
 * 对应 spec/skill.course-qa.md 第 4 节。
 */
@ConfigurationProperties(prefix = "qa")
public class QaProperties {

    private int chunkSize = 400;
    private int chunkOverlap = 50;

    /** bm25 | vector。默认 bm25：DeepSeek 无 embedding 接口，BM25 可离线、可解释。 */
    private String retrievalMode = "bm25";
    private int topK = 5;
    /** 向量模式的余弦阈值。 */
    private double minScore = 0.45;
    /** BM25 模式的原始分数阈值（量纲不同，单独配置）。 */
    private double bm25MinScore = 3.0;

    private String llmMode = "mock";
    private String llmBaseUrl = "";
    private String llmApiKey = "";
    private String llmModel = "";
    private double temperature = 0.2;
    private int maxContextChars = 3000;
    private int historyTurns = 3;

    /** 限流开关与参数（默认 30 次/分钟，对应验收标准 A8）。 */
    private boolean rateLimitEnabled = true;
    private int rateLimitCapacity = 30;
    private double rateLimitRefillPerSecond = 0.5;

    public int getChunkSize() { return chunkSize; }
    public void setChunkSize(int chunkSize) { this.chunkSize = chunkSize; }

    public int getChunkOverlap() { return chunkOverlap; }
    public void setChunkOverlap(int chunkOverlap) { this.chunkOverlap = chunkOverlap; }

    public String getRetrievalMode() { return retrievalMode; }
    public void setRetrievalMode(String retrievalMode) { this.retrievalMode = retrievalMode; }

    public int getTopK() { return topK; }
    public void setTopK(int topK) { this.topK = topK; }

    public double getMinScore() { return minScore; }
    public void setMinScore(double minScore) { this.minScore = minScore; }

    public double getBm25MinScore() { return bm25MinScore; }
    public void setBm25MinScore(double bm25MinScore) { this.bm25MinScore = bm25MinScore; }

    public String getLlmMode() { return llmMode; }
    public void setLlmMode(String llmMode) { this.llmMode = llmMode; }

    public String getLlmBaseUrl() { return llmBaseUrl; }
    public void setLlmBaseUrl(String llmBaseUrl) { this.llmBaseUrl = llmBaseUrl; }

    public String getLlmApiKey() { return llmApiKey; }
    public void setLlmApiKey(String llmApiKey) { this.llmApiKey = llmApiKey; }

    public String getLlmModel() { return llmModel; }
    public void setLlmModel(String llmModel) { this.llmModel = llmModel; }

    public double getTemperature() { return temperature; }
    public void setTemperature(double temperature) { this.temperature = temperature; }

    public int getMaxContextChars() { return maxContextChars; }
    public void setMaxContextChars(int maxContextChars) { this.maxContextChars = maxContextChars; }

    public int getHistoryTurns() { return historyTurns; }
    public void setHistoryTurns(int historyTurns) { this.historyTurns = historyTurns; }

    public boolean isRateLimitEnabled() { return rateLimitEnabled; }
    public void setRateLimitEnabled(boolean rateLimitEnabled) { this.rateLimitEnabled = rateLimitEnabled; }

    public int getRateLimitCapacity() { return rateLimitCapacity; }
    public void setRateLimitCapacity(int rateLimitCapacity) { this.rateLimitCapacity = rateLimitCapacity; }

    public double getRateLimitRefillPerSecond() { return rateLimitRefillPerSecond; }
    public void setRateLimitRefillPerSecond(double rateLimitRefillPerSecond) { this.rateLimitRefillPerSecond = rateLimitRefillPerSecond; }
}
