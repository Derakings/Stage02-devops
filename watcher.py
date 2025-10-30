#!/usr/bin/env python3
"""
Nginx Log Watcher - Monitors failovers and error rates
Sends alerts to Slack when thresholds are breached
"""

import re
import time
import os
import sys
from collections import deque
from datetime import datetime
import requests
import subprocess

# Configuration from environment variables
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ACTIVE_POOL = os.getenv('ACTIVE_POOL', 'blue')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2.0'))
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'
LOG_FILE = os.getenv('LOG_FILE', '/var/log/nginx/access.log')

# State tracking
current_pool = ACTIVE_POOL
last_pool = ACTIVE_POOL
request_window = deque(maxlen=WINDOW_SIZE)
last_alert_time = {'failover': 0, 'error_rate': 0, 'recovery': 0}

# Regex pattern to parse nginx log format
LOG_PATTERN = re.compile(
    r'pool=(?P<pool>\w+) '
    r'release=(?P<release>[\w\-\.]+) '
    r'upstream_status=(?P<upstream_status>\d+) '
    r'upstream_addr=(?P<upstream_addr>[\d\.:]+)'
)

def send_slack_alert(message, alert_type='info'):
    """Send alert to Slack with rate limiting"""
    if not SLACK_WEBHOOK_URL:
        print(f"[ALERT] {message}")
        return True
    
    # Check maintenance mode
    if MAINTENANCE_MODE and alert_type == 'failover':
        print(f"[MAINTENANCE MODE] Suppressing {alert_type} alert: {message}")
        return False
    
    # Check cooldown
    current_time = time.time()
    if current_time - last_alert_time.get(alert_type, 0) < ALERT_COOLDOWN_SEC:
        print(f"[COOLDOWN] Skipping {alert_type} alert (cooldown active)")
        return False
    
    # Icon mapping
    icons = {
        'failover': 'í´„',
        'error_rate': 'âš ï¸',
        'recovery': 'âœ…',
        'info': 'â„¹ï¸'
    }
    
    icon = icons.get(alert_type, 'í³¢')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    payload = {
        "text": f"{icon} *{alert_type.upper().replace('_', ' ')}*\n{message}\n_Time: {timestamp}_"
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code == 200:
            last_alert_time[alert_type] = current_time
            print(f"[SLACK SENT] {alert_type}: {message}")
            return True
        else:
            print(f"[SLACK ERROR] Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[SLACK ERROR] {e}")
        return False

def parse_log_line(line):
    """Extract relevant fields from log line"""
    match = LOG_PATTERN.search(line)
    if not match:
        return None
    
    return {
        'pool': match.group('pool'),
        'release': match.group('release'),
        'upstream_status': int(match.group('upstream_status')),
        'upstream_addr': match.group('upstream_addr')
    }

def calculate_error_rate():
    """Calculate 5xx error rate over sliding window"""
    if len(request_window) == 0:
        return 0.0
    
    error_count = sum(1 for status in request_window if status >= 500)
    return (error_count / len(request_window)) * 100

def detect_failover(new_pool):
    """Detect pool change (failover event)"""
    global current_pool, last_pool
    
    if new_pool != current_pool:
        old_pool = current_pool
        current_pool = new_pool
        last_pool = old_pool
        return True, old_pool, new_pool
    
    return False, None, None

def monitor_logs():
    """Main monitoring loop - tail nginx logs"""
    global current_pool
    
    print(f"íº€ Starting Nginx Log Watcher")
    print(f"   Log File: {LOG_FILE}")
    print(f"   Active Pool: {ACTIVE_POOL}")
    print(f"   Error Threshold: {ERROR_RATE_THRESHOLD}%")
    print(f"   Window Size: {WINDOW_SIZE} requests")
    print(f"   Alert Cooldown: {ALERT_COOLDOWN_SEC}s")
    print(f"   Maintenance Mode: {MAINTENANCE_MODE}")
    print(f"   Slack: {'Enabled' if SLACK_WEBHOOK_URL else 'Disabled (console only)'}")
    print("=" * 60)
    
    # Wait for log file to exist
    while not os.path.exists(LOG_FILE):
        print(f"Waiting for log file {LOG_FILE}...")
        time.sleep(2)
    
    # Start tailing the log file
    process = subprocess.Popen(
        ['tail', '-F', '-n', '0', LOG_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    try:
        for line in iter(process.stdout.readline, ''):
            if not line:
                continue
            
            # Parse log line
            data = parse_log_line(line.strip())
            if not data:
                continue
            
            pool = data['pool']
            status = data['upstream_status']
            
            # Track request in sliding window
            request_window.append(status)
            
            # Detect failover
            failover_detected, old_pool, new_pool = detect_failover(pool)
            if failover_detected:
                message = (
                    f"Failover Detected: {old_pool.upper()} â†’ {new_pool.upper()}\n"
                    f"Release: {data['release']}\n"
                    f"Upstream: {data['upstream_addr']}\n"
                    f"Action: Check {old_pool} container health immediately!"
                )
                send_slack_alert(message, alert_type='failover')
            
            # Check error rate (only after window is reasonably filled)
            if len(request_window) >= min(50, WINDOW_SIZE):
                error_rate = calculate_error_rate()
                
                if error_rate > ERROR_RATE_THRESHOLD:
                    message = (
                        f"High Error Rate: {error_rate:.2f}% (threshold: {ERROR_RATE_THRESHOLD}%)\n"
                        f"Current Pool: {pool.upper()}\n"
                        f"Window: Last {len(request_window)} requests\n"
                        f"Action: Investigate upstream logs and consider pool toggle!"
                    )
                    send_slack_alert(message, alert_type='error_rate')
            
            # Recovery detection - back to primary pool with low errors
            if pool == ACTIVE_POOL and current_pool == ACTIVE_POOL and last_pool != ACTIVE_POOL:
                error_rate = calculate_error_rate()
                if error_rate <= ERROR_RATE_THRESHOLD:
                    message = (
                        f"Recovery: {ACTIVE_POOL.upper()} pool restored\n"
                        f"Current Error Rate: {error_rate:.2f}%\n"
                        f"Status: System operating normally"
                    )
                    send_slack_alert(message, alert_type='recovery')
                    last_pool = ACTIVE_POOL
    
    except KeyboardInterrupt:
        print("\ní»‘ Shutting down watcher...")
        process.terminate()
    except Exception as e:
        print(f"âŒ Error: {e}")
        process.terminate()
        sys.exit(1)

if __name__ == '__main__':
    monitor_logs()
