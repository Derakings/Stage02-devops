# Operational Runbook

## Alert: Failover Detected 🔄

**Action:** Check the stopped container's health and logs.

```bash
docker logs app_blue --tail 50
docker restart app_blue