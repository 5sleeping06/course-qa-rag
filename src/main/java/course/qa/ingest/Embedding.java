package course.qa.ingest;

import java.util.Locale;

/**
 * 离线向量化：字符二元组哈希 + L2 归一化。
 *
 * 为什么先这么做（而不是一上来就调远程 embedding）：
 * 1) 让整条链路在没有 API Key、没有网络的情况下也能跑通、能被单测；
 * 2) 完全确定性，评测结果可复现，调参时不受远端模型波动影响；
 * 3) 报告里可以如实写成「开发期用本地哈希向量，生产用远程 embedding」的取舍。
 *
 * 缺点：只捕捉字面相似，不理解语义。D2 接入真实 embedding 后替换即可，
 * 检索接口不变（VectorStore.search 只依赖 float[] 与余弦相似度）。
 */
public final class Embedding {

    public static final int DIM = 512;

    private Embedding() {
    }

    public static float[] of(String text) {
        float[] v = new float[DIM];
        if (text == null || text.isEmpty()) {
            return v;
        }
        String s = text.toLowerCase(Locale.ROOT).replaceAll("\\s+", " ");
        for (int i = 0; i + 1 < s.length(); i++) {
            int h = (s.charAt(i) * 31 + s.charAt(i + 1)) & 0x7fffffff;
            v[h % DIM] += 1.0f;
        }
        double norm = 0.0;
        for (float x : v) {
            norm += x * x;
        }
        if (norm > 0) {
            float m = (float) Math.sqrt(norm);
            for (int i = 0; i < DIM; i++) {
                v[i] /= m;
            }
        }
        return v;
    }

    public static double cosine(float[] a, float[] b) {
        if (a == null || b == null || a.length != b.length) {
            return 0.0;
        }
        double dot = 0.0;
        for (int i = 0; i < a.length; i++) {
            dot += a[i] * b[i];
        }
        return dot; // 双方都已归一化，点积即余弦
    }
}
