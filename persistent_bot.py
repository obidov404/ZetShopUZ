#!/usr/bin/env python3
"""
Persistent runner for the Telegram bot with automatic restart
on crashes and detailed logging for diagnostics.

This version is optimized for running on Render.com with an integrated
health check server for monitoring.
"""

import os
import sys
import time
import json
import signal
import logging
import socketserver
import http.server
import subprocess
import threading
import requests
import psutil
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
MAX_RESTARTS = 20  # Maximum number of restarts in 24 hours
RESTART_DELAY = 10  # Seconds to wait between restarts
RESTART_BACKOFF_MAX = 300  # Maximum seconds to wait between restarts (5 minutes)
HEALTH_CHECK_PORT = int(os.environ.get('PORT', 8080))  # Port for health check

# State variables
termination_requested = False
restart_count = 0
restart_timestamps = []
current_process = None
health_check_thread = None

def handle_sigterm(signum, frame):
    """Handle termination signals gracefully"""
    global termination_requested
    logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
    termination_requested = True
    
    if current_process:
        logger.info("Terminating bot process...")
        try:
            current_process.terminate()
            time.sleep(2)
            if current_process.poll() is None:
                current_process.kill()
        except Exception as e:
            logger.error(f"Error terminating process: {e}")

# Register signal handlers
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

def calculate_restart_delay():
    """Calculate adaptive delay between restarts"""
    global restart_count, restart_timestamps
    
    now = datetime.now()
    restart_timestamps = [ts for ts in restart_timestamps if (now - ts).total_seconds() < 86400]
    restart_timestamps.append(now)
    restart_count = len(restart_timestamps)
    
    if restart_count > 1:
        # Exponential backoff
        delay = min(RESTART_DELAY * (2 ** (restart_count - 1)), RESTART_BACKOFF_MAX)
    else:
        delay = RESTART_DELAY
    
    return delay

def start_bot_process():
    """Start the bot process and return the subprocess object"""
    logger.info("Starting bot process...")
    
    # Get system stats before starting
    stats = get_system_stats()
    logger.info(f"System stats before start: {json.dumps(stats)}")
    
    try:
        process = subprocess.Popen(
            [sys.executable, "bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Start output readers
        for pipe, prefix in [(process.stdout, "OUT"), (process.stderr, "ERR")]:
            thread = threading.Thread(
                target=read_output,
                args=(pipe, prefix),
                daemon=True
            )
            thread.start()
        
        return process
    
    except Exception as e:
        logger.error(f"Error starting bot process: {e}")
        return None

def read_output(pipe, prefix):
    """Read output from the bot process"""
    try:
        for line in pipe:
            logger.info(f"{prefix}: {line.strip()}")
    except Exception as e:
        logger.error(f"Error reading {prefix}: {e}")

def get_system_stats():
    """Get basic system stats"""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return {
            "memory_percent": memory.percent,
            "memory_available": memory.available,
            "cpu_percent": psutil.cpu_percent(),
            "disk_percent": disk.percent,
            "disk_free": disk.free
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {}

def check_bot_status():
    """Check if the bot is working by calling the Telegram API"""
    bot_token = os.environ.get('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN not found, health checks disabled")
        return False
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=30
        )
        data = response.json()
        
        if data.get('ok'):
            logger.debug(f"Bot @{data['result']['username']} is online")
            return True, data['result']['username']
        else:
            logger.error(f"Bot check failed: {data.get('description', 'Unknown error')}")
            return False, None
    
    except Exception as e:
        logger.error(f"Error checking bot status: {e}")
        return False, None

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler for health checks"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            # Check bot status
            is_alive, bot_username = check_bot_status()
            
            # Get system stats
            stats = get_system_stats()
            
            # Prepare response
            status = "healthy" if is_alive else "unhealthy"
            response = {
                "status": status,
                "bot_username": bot_username,
                "timestamp": datetime.now().isoformat(),
                "restarts_24h": restart_count,
                "system_stats": stats
            }
            
            # Send response
            self.send_response(200 if is_alive else 503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        elif self.path == '/':
            # Serve HTML status page
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            
            # Get status info
            is_alive, bot_username = check_bot_status()
            status = "🟢 Online" if is_alive else "🔴 Offline"
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>ZetShopUz Bot Status</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 40px;
                        background: #f5f5f5;
                    }}
                    .container {{
                        max-width: 800px;
                        margin: 0 auto;
                        background: white;
                        padding: 20px;
                        border-radius: 10px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    h1 {{
                        color: #333;
                        margin-bottom: 20px;
                    }}
                    .status {{
                        font-weight: bold;
                        color: {is_alive and '#28a745' or '#dc3545'};
                    }}
                    .footer {{
                        margin-top: 20px;
                        color: #666;
                        font-size: 0.9em;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>ZetShopUz Telegram Bot</h1>
                    <p>Status: <span class="status">{status}</span></p>
                    <p>Bot Username: @{bot_username or 'Unknown'}</p>
                    <p>Last check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Restarts in last 24h: {restart_count}</p>
                    <div class="footer">
                        Powered by Render.com
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info("%s - %s" % (self.address_string(), format % args))

def run_health_check_server():
    """Run the health check HTTP server"""
    try:
        with socketserver.TCPServer(("0.0.0.0", HEALTH_CHECK_PORT), HealthCheckHandler) as httpd:
            logger.info(f"Health check server started at port {HEALTH_CHECK_PORT}")
            while not termination_requested:
                httpd.handle_request()
    except Exception as e:
        logger.error(f"Error running health server: {e}")
        time.sleep(5)

def main():
    """Main function to run the persistent bot with monitoring"""
    global current_process, health_check_thread, restart_count
    
    logger.info(f"Starting persistent bot runner on Render.com (Port: {HEALTH_CHECK_PORT})...")
    
    # Start the health check server
    health_check_thread = threading.Thread(target=run_health_check_server)
    health_check_thread.daemon = True
    health_check_thread.start()
    
    while not termination_requested:
        # Check if we've exceeded max restarts
        if restart_count >= MAX_RESTARTS:
            logger.critical(
                f"Maximum restarts ({MAX_RESTARTS}) exceeded in 24 hours. "
                "Waiting for 1 hour before trying again."
            )
            time.sleep(3600)  # Wait 1 hour
            restart_count = 0
            restart_timestamps.clear()
        
        # Start the bot process
        current_process = start_bot_process()
        if not current_process:
            logger.error("Failed to start bot process")
            time.sleep(RESTART_DELAY)
            continue
        
        # Wait for process to exit
        return_code = current_process.wait()
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if termination_requested:
            logger.info(f"Bot process terminated by request (code {return_code})")
            break
        
        # Log the restart
        logger.warning(
            f"Bot process exited with code {return_code} at {end_time}. "
            f"Restart count: {restart_count}"
        )
        
        # Calculate and apply restart delay
        delay = calculate_restart_delay()
        logger.info(f"Waiting {delay} seconds before restart...")
        
        # Wait for the delay period, checking for termination
        for _ in range(int(delay)):
            if termination_requested:
                break
            time.sleep(1)
    
    logger.info("Persistent bot runner stopped")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Runner stopped by keyboard interrupt")
    except Exception as e:
        logger.critical(f"Critical error in persistent runner: {e}", exc_info=True)
        sys.exit(1)
