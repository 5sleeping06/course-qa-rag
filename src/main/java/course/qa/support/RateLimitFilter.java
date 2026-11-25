package course.qa.support;

import com.fasterxml.jackson.databind.ObjectMapper;
import course.qa.config.QaProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 令牌桶限流：按客户端 IP 限制问答接口的调用频率。
 *
 * 为什么放在过滤器而不是控制器里：问答接口有两种（同步 / SSE），
 * 限流是横切关注点，放在最前面才能在进入业务逻辑之前就挡掉，避免白烧 token。
 *
 * 桶容量与补充速率可配置；默认 30 次/分（对应验收标准 A8）。
 * 压测时用 --qa.rate-limit.enabled=false 关闭，否则同 IP 的并发请求会被自己限住。
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(RateLimitFilter.class);
    private static final String RETRY_AFTER_SECONDS = "2";

    private final QaProperties props;
    private final ObjectMapper mapper;
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    public RateLimitFilter(QaProperties props, ObjectMapper mapper) {
        this.props = props;
        this.mapper = mapper;
        log.info("限流配置：enabled={}, capacity={}, refillPerSec={}",
                props.isRateLimitEnabled(), props.getRateLimitCapacity(), props.getRateLimitRefillPerSecond());
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (!props.isRateLimitEnabled() || !path.startsWith("/api/chat")) {
            chain.doFilter(request, response);
            return;
        }
        String key = clientIp(request);
        Bucket bucket = buckets.computeIfAbsent(key, k -> new Bucket(
                props.getRateLimitCapacity(), props.getRateLimitRefillPerSecond()));
        if (bucket.tryAcquire()) {
            chain.doFilter(request, response);
            return;
        }
        log.warn("触发限流: ip={} path={}", key, path);
        response.setStatus(429);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        response.setHeader("Retry-After", RETRY_AFTER_SECONDS);
        mapper.writeValue(response.getWriter(), Map.of(
                "code", "RATE_LIMITED",
                "message", "请求过于频繁，请稍后再试（默认 30 次/分钟）"));
    }

    private static String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    /** 简单令牌桶：容量 capacity，每秒补充 refillPerSecond 个令牌。 */
    static final class Bucket {
        private final double capacity;
        private final double refillPerSecond;
        private double tokens;
        private long lastRefillNanos;

        Bucket(int capacity, double refillPerSecond) {
            this.capacity = capacity;
            this.refillPerSecond = refillPerSecond;
            this.tokens = capacity;
            this.lastRefillNanos = System.nanoTime();
        }

        synchronized boolean tryAcquire() {
            long now = System.nanoTime();
            double elapsedSeconds = (now - lastRefillNanos) / 1_000_000_000.0;
            tokens = Math.min(capacity, tokens + elapsedSeconds * refillPerSecond);
            lastRefillNanos = now;
            if (tokens >= 1.0) {
                tokens -= 1.0;
                return true;
            }
            return false;
        }
    }
}
