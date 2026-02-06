"""
Real-time Application Logs Endpoint
Allows viewing live logs from the application
"""
import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from routes.admin_auth import verify_admin_session
import asyncio
from datetime import datetime

router = APIRouter()

# In-memory log storage (last 1000 lines)
log_buffer = []
MAX_LOG_LINES = 1000

class BufferHandler(logging.Handler):
    """Custom logging handler that stores logs in memory"""
    def emit(self, record):
        global log_buffer
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'logger': record.name,
            'message': self.format(record)
        }
        log_buffer.append(log_entry)
        # Keep only last MAX_LOG_LINES
        if len(log_buffer) > MAX_LOG_LINES:
            log_buffer.pop(0)

# Add buffer handler to root logger
buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(buffer_handler)

@router.get("/logs/view", response_class=HTMLResponse)
async def view_logs(request: Request, session: dict = Depends(verify_admin_session)):
    """View logs in browser"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Application Logs - SCOPE3</title>
        <style>
            body { 
                background: #0a0a0a; 
                color: #00ff00; 
                font-family: 'Courier New', monospace; 
                padding: 20px;
                margin: 0;
            }
            h1 { color: #00D9FF; }
            .log-container {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 20px;
                max-height: 80vh;
                overflow-y: auto;
            }
            .log-entry {
                margin: 5px 0;
                padding: 5px;
                border-left: 3px solid #444;
                padding-left: 10px;
            }
            .ERROR { border-left-color: #ff4444; color: #ff8888; }
            .WARNING { border-left-color: #ffaa00; color: #ffcc66; }
            .INFO { border-left-color: #00ff00; color: #88ff88; }
            .DEBUG { border-left-color: #888; color: #aaa; }
            .timestamp { color: #666; font-size: 0.9em; }
            .level { font-weight: bold; margin: 0 10px; }
            button {
                background: #00D9FF;
                color: #000;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                margin: 10px 5px;
            }
            button:hover { background: #00b3d9; }
        </style>
    </head>
    <body>
        <h1>📋 Application Logs</h1>
        <div>
            <button onclick="location.reload()">🔄 Refresh</button>
            <button onclick="clearLogs()">🗑️ Clear</button>
            <button onclick="location.href='/admin/dashboard'">← Back to Dashboard</button>
        </div>
        <div class="log-container" id="logs"></div>
        
        <script>
            async function loadLogs() {
                const response = await fetch('/admin/logs/api');
                const data = await response.json();
                const container = document.getElementById('logs');
                container.innerHTML = data.logs.map(log => `
                    <div class="log-entry ${log.level}">
                        <span class="timestamp">${log.timestamp}</span>
                        <span class="level">[${log.level}]</span>
                        <span class="logger">${log.logger}:</span>
                        <span class="message">${log.message}</span>
                    </div>
                `).join('');
                container.scrollTop = container.scrollHeight;
            }
            
            function clearLogs() {
                if (confirm('Clear all logs?')) {
                    fetch('/admin/logs/clear', {method: 'POST'});
                    setTimeout(loadLogs, 500);
                }
            }
            
            // Load logs on page load
            loadLogs();
            
            // Auto-refresh every 3 seconds
            setInterval(loadLogs, 3000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@router.get("/logs/api")
async def get_logs_api(session: dict = Depends(verify_admin_session)):
    """Get logs as JSON"""
    return {"logs": log_buffer}

@router.post("/logs/clear")
async def clear_logs(session: dict = Depends(verify_admin_session)):
    """Clear log buffer"""
    global log_buffer
    log_buffer = []
    return {"status": "success", "message": "Logs cleared"}
