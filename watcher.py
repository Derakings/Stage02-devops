#!/usr/bin/env python3
"""
Nginx Log Watcher - Monitors logs for failovers and error rates
Sends alerts to Slack when thresholds are breached
"""

import os
import re
import time
import json
import requests
from collections import deque
from datetime import datetime

# Configuration from environment
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2.0'))
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
LOG_FILE = '/var/log/nginx/access.log'

# State tracking
last_pool = None
last_failover_alert = 0
last_error_rate_alert = 0
request_window = deque(maxlen=WINDOW_SIZE)

# Log parsing regex
LOG_PATTERN = re.compile(
    r'pool=(?P<pool>\w+) '
    r'release=(?P<release>[\w\-\.]+) '
    r'upstream_status=(?P<upstream_status>\d+)'
)

def send_slack_alert(message, alert_type="info"):
    """Send alert to Slack webhook"""
    if not SLACK_WEBHOOK_URL:
        print(f"⚠️  No Slack webhook configured. Alert: {message}")
        return
    
    emoji = {
        "failover": "🔄",
        "error": "🚨",
        "recovery": "✅",
        "info": "ℹ️"
    }.get(alert_type, "📊")
    
    payload = {
        "text": f"{emoji} *{alert_type.upper()}*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Slack alert sent: {alert_type}")
    except Exception as e:
        print(f" Failed to send Slack alert: {e}")

def check_failover(pool):
    """Detect and alert on pool failover"""
    global last_pool, last_failover_alert
    
    if last_pool is None:
        last_pool = pool
        print(f"ℹ️  Initial pool: {pool}")
        return
    
    if pool != last_pool:
        # Check cooldown
        now = time.time()
        if now - last_failover_alert < ALERT_COOLDOWN_SEC:
            print(f"⏳ Failover detected but in cooldown period")
            return
        
        # Failover detected!
        message = (
            f"*Failover Detected: {last_pool.upper()} → {pool.upper()}*\n\n"
            f"• Previous Pool: `{last_pool}`\n"
            f"• Current Pool: `{pool}`\n"
            f"• Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
            f"*Action Required:* Check health of {last_pool} container"
        )
        
        send_slack_alert(message, "failover")
        last_pool = pool
        last_failover_alert = now

def check_error_rate():
    """Check if error rate exceeds threshold"""
    global last_error_rate_alert
    
    if len(request_window) < WINDOW_SIZE:
        return  # Not enough data yet
    
    error_count = sum(1 for status in request_window if status >= 500)
    error_rate = (error_count / len(request_window)) * 100
    
    if error_rate > ERROR_RATE_THRESHOLD:
        # Check cooldown
        now = time.time()
        if now - last_error_rate_alert < ALERT_COOLDOWN_SEC:
            return
        
        message = (
            f"*High Error Rate Alert*\n\n"
            f"• Error Rate: `{error_rate:.2f}%` (threshold: {ERROR_RATE_THRESHOLD}%)\n"
            f"• 5xx Errors: `{error_count}/{len(request_window)}` requests\n"
            f"• Window Size: `{WINDOW_SIZE}` requests\n\n"
            f"*Action Required:* Inspect upstream logs and consider toggling pools"
        )
        
        send_slack_alert(message, "error")
        last_error_rate_alert = now
        print(f"🚨 High error rate: {error_rate:.2f}%")

def tail_log_file():
    """Tail the Nginx log file and process entries"""
    print(f" Starting log watcher...")
    print(f" Config: ERROR_THRESHOLD={ERROR_RATE_THRESHOLD}%, WINDOW={WINDOW_SIZE}, COOLDOWN={ALERT_COOLDOWN_SEC}s")
    
    # Wait for log file to exist
    while not os.path.exists(LOG_FILE):
        print(f"⏳ Waiting for log file: {LOG_FILE}")
        time.sleep(5)
    
    print(f"✅ Log file found: {LOG_FILE}")
    
    with open(LOG_FILE, 'r') as f:
        # Seek to end of file
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            
            # Parse log line
            match = LOG_PATTERN.search(line)
            if not match:
                continue
            
            pool = match.group('pool')
            release = match.group('release')
            upstream_status = int(match.group('upstream_status'))
            
            # Track request status
            request_window.append(upstream_status)
            
            # Check for failover
            check_failover(pool)
            
            # Check error rate
            check_error_rate()
            
            print(f"📝 Request: pool={pool}, release={release}, status={upstream_status}")

if __name__ == '__main__':
    print("🚀 Nginx Log Watcher Starting...")
    try:
        tail_log_file()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        raise