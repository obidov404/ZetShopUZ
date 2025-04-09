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

# Load environment variables first
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='persistent_bot.log',
    filemode='a'
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

logger = logging.getLogger(__name__)

# Configuration
MAX_RESTARTS = 20  # Maximum number of restarts in 24 hours
RESTART_DELAY = 10  # Seconds to wait between restarts
RESTART_BACKOFF_MAX = 300  # Maximum seconds to wait between restarts (5 minutes)
REPLIT_KEEP_ALIVE_URL = os.environ.get('REPLIT_DB_URL', '').replace('db', 'keep-alive')
HEALTH_CHECK_PORT = int(os.environ.get('PORT', 8080))  # Port for health check (Render provides PORT env var)

# State variables
termination_requested = False
restart_count = 0
restart_timestamps = []
current_process = None
keep_alive_thread = None
health_check_thread = None

def handle_sigterm(signum, frame):
    """Handle termination signals gracefully"""
    global termination_requested
    logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
    termination_requested = True
    
    if current_process:
        logger.info("Terminating bot process...")
        try:
            # Try to terminate gracefully first
            current_process.terminate()
            time.sleep(2)  # Give it a moment to shut down
            
            # Force kill if still running
            if current_process.poll() is None:
                current_process.kill()
        except Exception as e:
            logger.error(f"Error terminating process: {e}")

# Register signal handlers
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

def replit_keep_alive():
    """Ping Replit keep-alive service to prevent the repl from sleeping"""
    if not REPLIT_KEEP_ALIVE_URL:
        logger.warning("REPLIT_DB_URL not found, keep-alive service not available")
        return
    
    while not termination_requested:
        try:
            response = requests.get(REPLIT_KEEP_ALIVE_URL)
            logger.debug(f"Keep-alive ping: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in keep-alive ping: {e}")
        
        # Wait 5 minutes before next ping
        for _ in range(300):  # 5 minutes in 1-second increments
            if termination_requested:
                break
            time.sleep(1)

def health_check():
    """Check if the bot is still responsive via the Telegram API"""
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.environ.get('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN not found, health checks disabled")
        return
    
    while not termination_requested:
        try:
            # Try to get bot info from Telegram API
            response = requests.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=30
            )
            data = response.json()
            
            if data.get('ok'):
                logger.debug(f"Health check: Bot @{data['result']['username']} is online")
            else:
                logger.error(f"Health check failed: {data.get('description', 'Unknown error')}")
                # Trigger restart if process exists
                if current_process and current_process.poll() is None:
                    logger.warning("Bot seems unresponsive, triggering restart...")
                    current_process.terminate()
        except Exception as e:
            logger.error(f"Error in health check: {e}")
        
        # Wait 10 minutes before next health check
        for _ in range(600):  # 10 minutes in 1-second increments
            if termination_requested:
                break
            time.sleep(1)

def calculate_restart_delay():
    """Calculate adaptive delay between restarts to prevent excessive cpu usage"""
    global restart_count, restart_timestamps
    
    # Keep only timestamps from the last 24 hours
    cutoff_time = time.time() - 86400  # 24 hours ago
    restart_timestamps = [ts for ts in restart_timestamps if ts > cutoff_time]
    
    # Add current timestamp
    restart_timestamps.append(time.time())
    restart_count = len(restart_timestamps)
    
    # Calculate delay based on recent restart frequency
    if restart_count <= 3:
        return RESTART_DELAY
    elif restart_count <= 5:
        return min(RESTART_DELAY * 2, RESTART_BACKOFF_MAX)
    elif restart_count <= 10:
        return min(RESTART_DELAY * 4, RESTART_BACKOFF_MAX)
    else:
        return RESTART_BACKOFF_MAX

def start_bot_process():
    """Start the bot process and return the subprocess object"""
    logger.info("Starting bot process...")
    
    # Build the command with explicit python path
    cmd = [sys.executable, "bot_runner.py"]
    
    # Start the process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1  # Line buffered
    )
    
    # Start stdout/stderr readers in separate threads
    def read_output(pipe, prefix):
        for line in pipe:
            logger.info(f"{prefix}: {line.strip()}")
    
    threading.Thread(target=read_output, args=(process.stdout, "BOT_OUT"), daemon=True).start()
    threading.Thread(target=read_output, args=(process.stderr, "BOT_ERR"), daemon=True).start()
    
    logger.info(f"Bot process started with PID {process.pid}")
    return process

def get_system_stats():
    """Get basic system stats"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_usage,
            "disk_percent": disk_usage,
            "memory_available_mb": round(memory.available / (1024 * 1024), 2),
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {"error": str(e)}


def check_bot_status():
    """Check if the bot is working by calling the Telegram API"""
    bot_token = os.environ.get('BOT_TOKEN')
    if not bot_token:
        return {"status": "error", "message": "BOT_TOKEN not set"}
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                return {
                    "status": "online",
                    "bot_id": bot_info.get("id"),
                    "bot_name": bot_info.get("first_name"),
                    "bot_username": bot_info.get("username"),
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000)
                }
        
        return {
            "status": "error",
            "http_status": response.status_code,
            "message": f"API returned: {response.text}"
        }
    
    except requests.RequestException as e:
        return {"status": "error", "message": f"API request failed: {str(e)}"}


class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler for health checks"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            start_time = datetime.now()
            uptime = datetime.now() - start_time
            
            health_data = {
                "status": "ok",
                "uptime": str(uptime),
                "timestamp": datetime.now().isoformat(),
                "host": self.headers.get('Host', 'unknown'),
                "system": get_system_stats(),
                "bot": check_bot_status(),
                "process": {
                    "status": "running" if current_process and current_process.poll() is None else "not_running",
                    "pid": current_process.pid if current_process else None,
                    "restart_count": restart_count
                }
            }
            
            # Determine overall health status
            if (health_data["bot"]["status"] != "online" or
                health_data["process"]["status"] != "running"):
                health_data["status"] = "degraded"
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_data, indent=2).encode())
            
        elif self.path == '/' or self.path == '/status':
            # A simpler status page that just says the bot is running
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            status = "Running" if current_process and current_process.poll() is None else "Stopped"
            color = "green" if status == "Running" else "red"
            
            bot_info = check_bot_status()
            bot_username = bot_info.get("bot_username", "Unknown")
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>ZetShopUz Bot Status</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    h1 {{ color: #333; margin-top: 0; }}
                    .status {{ display: inline-block; padding: 6px 12px; border-radius: 4px; color: white; background-color: {color}; }}
                    p {{ color: #666; }}
                    .footer {{ margin-top: 30px; font-size: 0.8rem; color: #999; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>ZetShopUz Telegram Bot</h1>
                    <p>Status: <span class="status">{status}</span></p>
                    <p>Bot Username: @{bot_username}</p>
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


def run_health_server():
    """Run the health check HTTP server"""
    try:
        with socketserver.TCPServer(("0.0.0.0", HEALTH_CHECK_PORT), HealthCheckHandler) as httpd:
            logger.info(f"Health check server started at port {HEALTH_CHECK_PORT}")
            while not termination_requested:
                httpd.handle_request()
    except Exception as e:
        logger.error(f"Error running health server: {e}")
        time.sleep(5)  # Wait a bit before potential restart


def main():
    """Main function to run the persistent bot with monitoring"""
    global current_process, keep_alive_thread, health_check_thread, restart_count
    
    # Initialize restart counter
    restart_count = 0
    
    logger.info(f"Starting persistent bot runner on Render.com (Port: {HEALTH_CHECK_PORT})...")
    
    # Start health check server in a separate thread
    health_server_thread = threading.Thread(target=run_health_server, daemon=True)
    health_server_thread.start()
    logger.info(f"Health check server started at http://0.0.0.0:{HEALTH_CHECK_PORT}/health")
    
    # Start keep-alive ping to Replit (only if needed)
    if REPLIT_KEEP_ALIVE_URL:
        keep_alive_thread = threading.Thread(target=replit_keep_alive, daemon=True)
        keep_alive_thread.start()
    
    # Start health check thread
    health_check_thread = threading.Thread(target=health_check, daemon=True)
    health_check_thread.start()
    
    while not termination_requested:
        # Check if we've exceeded max restarts
        if restart_count >= MAX_RESTARTS:
            logger.critical(
                f"Maximum restarts ({MAX_RESTARTS}) exceeded in 24 hours. "
                "Waiting for 1 hour before trying again to prevent abuse."
            )
            time.sleep(3600)  # Wait 1 hour
            restart_count = 0  # Reset counter after waiting
            restart_timestamps.clear()
        
        # Start the bot process
        current_process = start_bot_process()
        
        # Wait for process to exit
        return_code = current_process.wait()
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if termination_requested:
            logger.info(f"Bot process terminated by request (code {return_code})")
            break
        
        # Log the restart
        logger.warning(
            f"Bot process exited with code {return_code} at {end_time}. "
            f"Restart count: {restart_count + 1}"
        )
        
        # Calculate and apply restart delay
        delay = calculate_restart_delay()
        logger.info(f"Waiting {delay} seconds before restart...")
        
        # Wait for the delay period, checking for termination every second
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
