# Blue/Green Deployment with Nginx Auto-Failover

## 🎯 Overview
This project implements a Blue/Green deployment strategy for a Node.js service with Nginx as a reverse proxy. It provides automatic failover from Blue to Green when the active service fails.

## 🏗️ Architecture
```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Nginx :8080   │
                  │  (Smart Guard) │
                  └────────┬───────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  Blue :8081      │      │  Green :8082     │
    │  (Primary)       │      │  (Backup)        │
    └──────────────────┘      └──────────────────┘
```

## 📋 Prerequisites
- Docker & Docker Compose installed
- Ports 8080, 8081, 8082 available

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Derakings/your-repo-name.git
cd your-repo-name
```

### 2. Set up environment variables
```bash
cp .env.example .env
```

### 3. Start the services
```bash
docker-compose up -d
```

### 4. Verify it's working
```bash
# Check Blue is active
curl http://localhost:8080/version

# Expected response:
# {
#   "version": "1.0.0",
#   "pool": "blue"
# }
# 
# Headers should include:
# X-App-Pool: blue
# X-Release-Id: blue-v1.0
```

## 🧪 Testing Failover

### Trigger Blue failure
```bash
# Simulate Blue service failure
curl -X POST http://localhost:8081/chaos/start?mode=error
```

### Verify automatic switch to Green
```bash
# This should now return Green without any errors
curl http://localhost:8080/version

# Expected response:
# {
#   "version": "1.0.0",
#   "pool": "green"
# }
# 
# Headers should include:
# X-App-Pool: green
# X-Release-Id: green-v1.0
```

### Stop chaos and restore Blue
```bash
curl -X POST http://localhost:8081/chaos/stop
```

## 🔄 Manual Pool Switching

To manually switch the active pool:

1. Edit `.env` and change `ACTIVE_POOL`:
```bash
ACTIVE_POOL=green  # Switch to green
```

2. Reload Nginx configuration:
```bash
docker-compose exec nginx /reload-nginx.sh
```

## 📊 Monitoring

### Check service health
```bash
# Check Blue health
curl http://localhost:8081/healthz

# Check Green health
curl http://localhost:8082/healthz

# Check through Nginx
curl http://localhost:8080/healthz
```

### View Nginx logs
```bash
docker-compose logs -f nginx
```

### View application logs
```bash
# Blue logs
docker-compose logs -f app_blue

# Green logs
docker-compose logs -f app_green
```

## 🛠️ Configuration

### Environment Variables (.env)
- `BLUE_IMAGE` - Docker image for Blue service
- `GREEN_IMAGE` - Docker image for Green service
- `ACTIVE_POOL` - Active pool (blue or green)
- `RELEASE_ID_BLUE` - Release identifier for Blue
- `RELEASE_ID_GREEN` - Release identifier for Green
- `PORT` - Application port (default: 3000)

### Nginx Configuration
The Nginx configuration uses:
- **Primary/Backup strategy**: Blue is primary, Green is backup
- **Fast failover**: max_fails=1, fail_timeout=10s
- **Retry logic**: Retries on error, timeout, and 5xx responses
- **Tight timeouts**: 2s connect, 3s read, 5s overall

## 🎭 Chaos Modes

The application supports different chaos modes:

```bash
# Return 500 errors
curl -X POST http://localhost:8081/chaos/start?mode=error

# Timeout (slow responses)
curl -X POST http://localhost:8081/chaos/start?mode=timeout

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

## 📝 API Endpoints

### Through Nginx (http://localhost:8080)
- `GET /version` - Get version and pool info
- `GET /healthz` - Health check

### Direct Access (for chaos testing)
- `POST http://localhost:8081/chaos/start?mode=error` - Break Blue
- `POST http://localhost:8081/chaos/stop` - Restore Blue
- `POST http://localhost:8082/chaos/start?mode=error` - Break Green
- `POST http://localhost:8082/chaos/stop` - Restore Green

## 🔍 Troubleshooting

### Services won't start
```bash
# Check if ports are in use
lsof -i :8080
lsof -i :8081
lsof -i :8082

# Stop and remove containers
docker-compose down
docker-compose up -d
```

### Failover not working
```bash
# Check Nginx configuration
docker-compose exec nginx nginx -t

# Reload Nginx
docker-compose exec nginx nginx -s reload
```

### Headers not showing
```bash
# Use verbose curl to see all headers
curl -v http://localhost:8080/version
```

## 📦 Project Structure
```
.
├── docker-compose.yml       # Service orchestration
├── nginx.conf.template      # Nginx configuration template
├── reload-nginx.sh          # Script to reload Nginx config
├── .env.example             # Example environment variables
├── .env                     # Your environment variables (gitignored)
├── README.md               # This file
└── DECISION.md             # Design decisions (optional)
```

## 🎯 Success Criteria

✅ Zero failed requests during failover  
✅ Automatic switch from Blue to Green within 10s  
✅ Headers properly forwarded (X-App-Pool, X-Release-Id)  
✅ ≥95% of requests served by backup after failover  

## 📚 Additional Resources
- [Nginx Upstream Documentation](http://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## 👤 Author
Derakings

## 📄 License
MIT
```