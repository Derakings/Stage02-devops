# Blue/Green Deployment with Nginx Auto-Failover

## Overview
This project implements a Blue/Green deployment strategy for a Node.js service with Nginx as a reverse proxy, providing automatic failover with zero downtime.

## Architecture
- **Nginx** (port 8080): Reverse proxy and load balancer
- **Blue Service** (port 8081): Primary application instance
- **Green Service** (port 8082): Backup application instance

Traffic flows through Nginx, which automatically routes requests to Blue by default. When Blue fails, Nginx immediately switches to Green without dropping requests.

## Prerequisites
- Docker
- Docker Compose
- Ports 8080, 8081, 8082 available

## Quick Start

### Setup
```bash
# Clone repository
git clone https://github.com/Derakings/stage02-devops.git
cd stage02-devops

# Configure environment
cp .env.example .env

# Run Automated shell script
chmod +x test.sh

./test.sh
```
**The test script automatically verifies:**
- ✅ Blue is active by default
- ✅ Chaos mode activation
- ✅ Automatic failover to Green
- ✅ Zero failed requests during chaos (10/10 successful)
- ✅ 100% uptime maintained
- ✅ Automatic recovery to Blue after chaos ends
