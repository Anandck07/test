import subprocess
import sys
import os
import time
import signal
import logging
import threading
import socket
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ProcessManager')

# Create recordings directory
recordings_dir = 'recordings'
if not os.path.exists(recordings_dir):
    os.makedirs(recordings_dir)
    logger.info(f"Created recordings directory: {recordings_dir}")

# Create config directory if needed
config_dir = 'config'
if not os.path.exists(config_dir):
    os.makedirs(config_dir)
    logger.info(f"Created config directory: {config_dir}")

# Create or update config file
config_path = os.path.join(config_dir, 'config.yaml')
if not os.path.exists(config_path):
    # Create default config
    default_config = {
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        },
        'api': {
            'host': 'localhost',
            'port': 8081
        },
        'cameras': [],
        'analytics': {
            'idle_threshold_seconds': 300,
            'unauthorized_alert_threshold': 60
        },
        'zones': {
            'desk_areas': [
                {'name': 'Desk Area 1', 'type': 'desk', 'max_capacity': 4},
                {'name': 'Desk Area 2', 'type': 'desk', 'max_capacity': 4}
            ],
            'meeting_rooms': [
                {'name': 'Meeting Room 1', 'type': 'meeting', 'max_capacity': 8},
                {'name': 'Meeting Room 2', 'type': 'meeting', 'max_capacity': 6}
            ],
            'break_areas': [
                {'name': 'Break Area 1', 'type': 'break', 'max_capacity': 10}
            ]
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(default_config, f)
    logger.info(f"Created default config file: {config_path}")

def is_port_in_use(port, host='0.0.0.0'):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except socket.error:
            return True

class CameraAPIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type='application/json'):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.end_headers()
        
    def do_GET(self):
        if self.path == '/cameras':
            # Load config to get current cameras
            try:
                with open('config/config.yaml', 'r') as f:
                    config = yaml.safe_load(f)
                cameras = config.get('cameras', [])
                
                self._set_headers()
                self.wfile.write(json.dumps(cameras).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
            
    def do_POST(self):
        if self.path == '/cameras/add':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Parse the JSON data
                camera_data = json.loads(post_data.decode('utf-8'))
                
                # Load the current config
                with open('config/config.yaml', 'r') as f:
                    config = yaml.safe_load(f)
                
                # Add new camera
                new_camera = {
                    'id': f"cam{len(config['cameras']) + 1}",
                    'name': camera_data.get('camera_name', f"Camera {len(config['cameras']) + 1}"),
                    'url': camera_data.get('camera_url'),
                    'zone_type': camera_data.get('zone_type', 'other'),
                    'active': True
                }
                
                config['cameras'].append(new_camera)
                
                # Save updated config
                with open('config/config.yaml', 'w') as f:
                    yaml.dump(config, f)
                
                # Return success response
                self._set_headers()
                self.wfile.write(json.dumps({'status': 'success', 'camera': new_camera}).encode())
                
            except Exception as e:
                logger.error(f"Error adding camera: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

class APIServer:
    def __init__(self, port=8081):
        self.port = port
        self.server = None
        self.server_thread = None
        self.is_running = False
    
    def start(self):
        """Start the API server."""
        try:
            self.server = HTTPServer(('localhost', self.port), CameraAPIHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.is_running = True
            logger.info(f"API server started on port {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start API server: {str(e)}")
            return False
    
    def shutdown(self):
        """Shutdown the API server."""
        if self.server:
            self.server.shutdown()
            self.is_running = False
            logger.info("API server stopped")

class DashboardRunner:
    def __init__(self):
        self.process = None
        self.is_running = False
    
    def start_dashboard(self, port=8502):
        """Start the Streamlit dashboard."""
        logger.info(f"Starting dashboard on port {port}...")
        
        # Start the dashboard process
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'streamlit', 'run', 'src/dashboard/app.py', 
             '--server.headless=true', '--server.runOnSave=false', f'--server.port={port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Start output monitoring threads
        threading.Thread(target=self._monitor_output, args=(self.process.stdout, 'stdout')).start()
        threading.Thread(target=self._monitor_output, args=(self.process.stderr, 'stderr')).start()
        
        return self.process
    
    def _monitor_output(self, pipe, pipe_type):
        """Monitor process output and print it."""
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    print(f"[Dashboard-{pipe_type}] {line.strip()}")
        except Exception as e:
            logger.error(f"Error monitoring dashboard {pipe_type}: {str(e)}")
    
    def shutdown(self):
        """Clean up the running process."""
        if not self.process:
            return
            
        logger.info("\nShutting down dashboard...")
        self.is_running = False
        
        if self.process.poll() is None:  # Process is still running
            try:
                # Try graceful termination first
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Dashboard did not terminate gracefully, forcing...")
                self.process.kill()
                self.process.wait()
    
    def monitor(self):
        """Monitor the dashboard process."""
        self.is_running = True
        
        logger.info("Dashboard is running. Press Ctrl+C to stop.")
        
        try:
            while self.is_running and self.process.poll() is None:
                time.sleep(0.5)
                
            if self.process.poll() is not None:
                logger.error("Dashboard has stopped unexpectedly!")
                return False
                
            return True
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt.")
            return True

def main():
    """Run the webcam management dashboard."""
    # Find available port for API
    api_port = 8081
    if is_port_in_use(api_port):
        logger.warning(f"API port {api_port} is already in use. Trying to find an alternative port.")
        # Try to find an available port
        for port in range(8082, 8100):
            if not is_port_in_use(port):
                api_port = port
                logger.info(f"Found available port for API: {api_port}")
                
                # Update config with new API port
                try:
                    with open('config/config.yaml', 'r') as f:
                        config = yaml.safe_load(f)
                    
                    config['api']['port'] = api_port
                    
                    with open('config/config.yaml', 'w') as f:
                        yaml.dump(config, f)
                        
                    logger.info(f"Updated config with new API port: {api_port}")
                except Exception as e:
                    logger.error(f"Error updating config: {str(e)}")
                
                break
        else:
            logger.error("Could not find an available port for API. Exiting.")
            return
    
    # Start API server
    api_server = APIServer(port=api_port)
    if not api_server.start():
        logger.error("Failed to start API server. Exiting.")
        return
    
    # Find available port for Streamlit
    streamlit_port = 8502
    if is_port_in_use(streamlit_port):
        logger.warning(f"Port {streamlit_port} is already in use. Trying to find an alternative port.")
        # Try to find an available port
        for port in range(8503, 8520):
            if not is_port_in_use(port):
                streamlit_port = port
                logger.info(f"Found available port: {streamlit_port}")
                break
        else:
            logger.error("Could not find an available port. Exiting.")
            api_server.shutdown()
            return
    
    # Create dashboard runner
    runner = DashboardRunner()
    
    try:
        # Start the dashboard
        runner.start_dashboard(port=streamlit_port)
        
        # Print access URL
        logger.info(f"Dashboard is running at: http://localhost:{streamlit_port}")
        logger.info("Press Ctrl+C to stop the dashboard")
        
        # Monitor the dashboard
        runner.monitor()
        
    except Exception as e:
        logger.error(f"Error running dashboard: {str(e)}")
    finally:
        runner.shutdown()
        api_server.shutdown()

if __name__ == "__main__":
    main() 