# Design Decisions & Implementation Notes

## 🎯 Overview
This document explains the key decisions made during the implementation of the Blue/Green deployment with Nginx auto-failover.

## 🏗️ Architecture Decisions

### 1. **Primary/Backup Strategy**
**Decision:** Use Nginx's `backup` directive instead of weighted load balancing.

**Reasoning:**
- The task explicitly requires Blue to be active by default
- All traffic should go to Blue in normal state
- Green should only receive traffic when Blue fails
- The `backup` directive ensures Green is only used when the primary is unavailable

**Implementation:**
```nginx
upstream backend {
    server app_blue:3000 max_fails=1 fail_timeout=10s;
    server app_green:3000 backup;
}
```

### 2. **Aggressive Failover Timeouts**
**Decision:** Set very tight timeouts for fast failure detection.

**Reasoning:**
- Task requires failover within 10 seconds
- Default Nginx timeouts are too long (60s+)
- Need to detect failures quickly to minimize client impact

**Timeouts chosen:**
- `proxy_connect_timeout: 2s` - Fast connection attempt
- `proxy_read_timeout: 3s` - Quick failure detection
- `proxy_next_upstream_timeout: 5s` - Overall retry window
- `max_fails: 1` - Single failure triggers failover
- `fail_timeout: 10s` - How long server stays marked as failed

### 3. **Comprehensive Retry Policy**
**Decision:** Retry on `error`, `timeout`, and all 5xx HTTP codes.

**Reasoning:**
- Chaos mode triggers both timeouts and 5xx errors
- Need to catch all failure scenarios
- `proxy_next_upstream` directive covers:
  - Network errors
  - Connection timeouts
  - HTTP 500, 502, 503, 504

**Implementation:**
```nginx
proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
proxy_next_upstream_tries 2;
```

### 4. **Header Forwarding**
**Decision:** Use `proxy_pass_header` for application headers.

**Reasoning:**
- Task requires X-App-Pool and X-Release-Id to reach clients
- Nginx sometimes hides custom headers by default
- Explicit `proxy_pass_header` ensures they're preserved

### 5. **Docker Networking**
**Decision:** Use custom bridge network instead of default network.

**Reasoning:**
- Better DNS resolution between containers
- Container names act as hostnames (app_blue, app_green)
- Isolation from other Docker projects

### 6. **Direct Port Exposure**
**Decision:** Expose Blue (8081) and Green (8082) directly to host.

**Reasoning:**
- Task requires grader to trigger chaos on specific instances
- Need direct access to POST /chaos/start
- Doesn't break the "must use Nginx" rule for normal traffic

##  Configuration Management

### 7. **Environment-based Configuration**
**Decision:** Use `.env` file for all parameterization.

**Reasoning:**
- Task explicitly requires full parameterization
- CI/grader needs to set variables without editing files
- Docker Compose natively supports .env files
- Easy to swap images and configurations

### 8. **Template-based Nginx Config**
**Decision:** Use `nginx.conf.template` with `envsubst`.

**Reasoning:**
- Allows runtime configuration changes
- Can switch ACTIVE_POOL without rebuilding
- Supports manual toggle requirement
- Standard Nginx approach

## 🧪 Testing Considerations

### 9. **Health Check Implementation**
**Decision:** Add Docker health checks to both services.

**Reasoning:**
- Visibility into container health
- Docker can restart unhealthy containers
- Helps with debugging
- A good practice

### 10. **Logging Strategy**
**Decision:** Use Nginx's default logging with upstream information.

**Reasoning:**
- Can trace which backend handled each request
- Helpful for debugging failover behavior
- Standard format for log analysis tools

##  Edge Cases Handled

### 11. **Race Conditions**
**Problem:** What if both Blue and Green fail simultaneously?

**Solution:**
- Each service has independent health checks
- Docker restarts unhealthy containers
- Nginx will return 502 if all upstreams are down
- This is expected behavior (can't serve if nothing works)

### 12. **Startup Order**
**Problem:** Nginx might start before apps are ready.

**Solution:**
- Used `depends_on` in docker-compose
- Services have health checks with `start_period`
- Nginx retry logic handles temporary unavailability
- In production, would use wait-for-it script

### 13. **Port Conflicts**
**Problem:** Ports 8080, 8081, 8082 might be in use.

**Solution:**
- Document port requirements in README
- Could make ports configurable via .env if needed
- Task specifies these exact ports, so must be available

## 🎨 Alternative Approaches Considered

### Not Chosen: Health Check-based Routing
**Why not:** Nginx open-source doesn't have active health checks (Nginx Plus feature). Passive health checks (max_fails) are sufficient for this task.

### Not Chosen: Lua Scripting
**Why not:** Adds complexity; native Nginx features are sufficient for the requirements.

### Not Chosen: Multiple Nginx Configs
**Why not:** Template approach is cleaner and supports runtime updates.

## 📊 Performance Characteristics

### Expected Behavior:
- **Normal state:** All requests → Blue, 0ms overhead
- **During failover:** 2-5s total latency for failing request
- **After failover:** All requests → Green, 0ms overhead
- **Zero failed requests** (client sees retry transparently)

### Bottlenecks:
- Failover speed limited by timeout settings
- Trade-off: Tighter timeouts = faster failover but more false positives
- Current settings optimized for task requirements

## 🔮 Future Improvements

If this were production:
1. Add Prometheus metrics
2. Implement graceful shutdown hooks
3. Add integration tests
4. Use Nginx Plus for active health checks
5. Add circuit breaker pattern
6. Implement gradual traffic shift (canary)

## ✅ Task Requirement Compliance

| Requirement | Implementation | Status |
|------------|----------------|---------|
| Blue active by default | `backup` directive | ✅ |
| Auto-failover on failure | `max_fails=1` + retry | ✅ |
| Zero failed requests | `proxy_next_upstream` | ✅ |
| Forward headers | `proxy_pass_header` | ✅ |
| Parameterized via .env | All variables in .env | ✅ |
| Direct port access | Exposed 8081, 8082 | ✅ |
| No image building | Pre-built images only | ✅ |
| Docker Compose | docker-compose.yml | ✅ |

## 👤 Author Notes

**What I learned:**
- Nginx's passive health checking is powerful
- Timeout tuning is critical for failover speed
- Docker networking simplifies service discovery

**What I'd do differently:**
- Add automated integration tests
- Create a monitoring dashboard
- Script the entire test suite

**Time spent:** ~2-3 hours (research, implementation, testing)