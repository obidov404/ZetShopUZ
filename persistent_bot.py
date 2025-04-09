#!/usr/bin/env python3
"""
Persistent runner for the Telegram bot with automatic restart
on crashes and detailed logging for diagnostics.
"""

import os
import sys
import time
import logging
import subprocess
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
HEALTH_CHECK_PORT = int(os.environ.get('PORT', 8080))
MAX_RESTARTS = 10
RESTART_DELAY = 10

# Global variables
bot_process = None
should_stop = False

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        logger.info("%s - %s" % (self.address_string(), format % args))

def run_health_server():
    """Run the health check server"""
    server = HTTPServer(('0.0.0.0', HEALTH_CHECK_PORT), HealthCheckHandler)
    logger.info(f"Health check server started on port {HEALTH_CHECK_PORT}")
    server.serve_forever()

def read_output(pipe, prefix):
    """Read output from the bot process"""
    for line in pipe:
        logger.info(f"{prefix}: {line.strip()}")

def start_bot():
    """Start the bot process"""
    try:
        # Kill any existing python processes running bot.py
        os.system('taskkill /f /im python.exe 2>nul')
        
        # Wait a moment for processes to clean up
        time.sleep(2)
        
        # Start new bot process
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
        logger.error(f"Error starting bot: {e}")
        return None

def main():
    """Main function"""
    global bot_process, should_stop
    
    try:
        # Start health check server
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()
        
        restart_count = 0
        while not should_stop and restart_count < MAX_RESTARTS:
            logger.info(f"Starting bot (attempt {restart_count + 1}/{MAX_RESTARTS})")
            
            bot_process = start_bot()
            if not bot_process:
                logger.error("Failed to start bot")
                time.sleep(RESTART_DELAY)
                continue
            
            try:
                # Wait for process to exit
                exit_code = bot_process.wait()
                logger.info(f"Bot exited with code {exit_code}")
                
                if exit_code == 0:
                    # Clean exit, no need to restart
                    logger.info("Bot exited cleanly. Stopping.")
                    break
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                should_stop = True
                break
            
            if should_stop:
                break
            
            restart_count += 1
            if restart_count < MAX_RESTARTS:
                logger.info(f"Restarting in {RESTART_DELAY} seconds...")
                time.sleep(RESTART_DELAY)
        
        if restart_count >= MAX_RESTARTS:
            logger.error(f"Maximum restarts ({MAX_RESTARTS}) reached. Stopping.")
            
    finally:
        # Cleanup
        if bot_process and bot_process.poll() is None:
            logger.info("Terminating bot process...")
            bot_process.terminate()
            try:
                bot_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Bot process did not terminate, forcing...")
                bot_process.kill()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        should_stop = True
        if bot_process:
            bot_process.terminate()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1)
