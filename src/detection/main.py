import cv2
import yaml
import time
from detector import PersonDetector
import redis
import json
from datetime import datetime
import threading
import queue
import logging
import sys
import os
import base64
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('DetectionService')

class DetectionService:
    def __init__(self, config_path: str = "config/config.yaml"):
        try:
            # Load configuration
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            # Initialize detector
            logger.info("Initializing person detector...")
            self.detector = PersonDetector(config_path)
            
            # Initialize Redis connection
            logger.info("Connecting to Redis...")
            try:
                self.redis_client = redis.Redis(
                    host=self.config['redis']['host'],
                    port=self.config['redis']['port'],
                    db=self.config['redis']['db']
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Successfully connected to Redis")
            except:
                logger.warning("Redis connection failed. Using mock Redis for development.")
                # Mock Redis implementation for development
                class MockRedis:
                    def __init__(self):
                        self.data = {}
                        self.pubsub_channels = {}
                        
                    def get(self, key):
                        return self.data.get(key)
                        
                    def set(self, key, value):
                        self.data[key] = value
                        return True
                        
                    def publish(self, channel, message):
                        logger.info(f"Mock Redis: Publishing to {channel}")
                        if channel not in self.pubsub_channels:
                            self.pubsub_channels[channel] = []
                        self.pubsub_channels[channel].append(message)
                        return 1
                        
                    def ping(self):
                        return True
                    
                    def close(self):
                        pass
                
                self.redis_client = MockRedis()
            
            # Initialize video capture
            logger.info("Initializing video capture...")
            camera_config = self.config['cameras'][0]
            self.simulation_mode = camera_config.get('simulation_mode', False)
            
            if not self.simulation_mode:
                self.cap = cv2.VideoCapture(camera_config['source'])
                if not self.cap.isOpened():
                    logger.warning(f"Failed to open camera {camera_config['source']}. Falling back to simulation mode.")
                    self.simulation_mode = True
                else:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_config['resolution'][0])
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_config['resolution'][1])
            
            if self.simulation_mode:
                logger.info("Running in simulation mode with synthetic frames")
                # Create a blank frame for simulation
                self.frame_width = camera_config['resolution'][0]
                self.frame_height = camera_config['resolution'][1]
                self.simulation_frame_count = 0
            
            # Initialize frame queue for processing
            self.frame_queue = queue.Queue(maxsize=10)
            self.result_queue = queue.Queue(maxsize=10)
            
            # Initialize processing thread
            self.processing_thread = None
            self.is_running = False
            
            logger.info("Detection service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing detection service: {str(e)}")
            raise
    
    def _get_simulation_frame(self):
        """Generate a synthetic frame for simulation mode."""
        # Create a blank frame
        frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        
        # Add some text
        cv2.putText(frame, "Simulation Mode", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Frame: {self.simulation_frame_count}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Draw simulated person
        x = int(self.frame_width/2 + 100 * np.sin(self.simulation_frame_count / 30))
        y = int(self.frame_height/2 + 100 * np.cos(self.simulation_frame_count / 30))
        cv2.circle(frame, (x, y), 30, (0, 0, 255), -1)
        
        self.simulation_frame_count += 1
        return frame
    
    def start(self):
        """Start the detection service."""
        try:
            self.is_running = True
            
            # Start processing thread
            logger.info("Starting processing thread...")
            self.processing_thread = threading.Thread(target=self._process_frames)
            self.processing_thread.start()
            
            # Main loop
            logger.info("Starting main detection loop...")
            while self.is_running:
                if self.simulation_mode:
                    frame = self._get_simulation_frame()
                    ret = True
                else:
                    ret, frame = self.cap.read()
                
                if not ret:
                    logger.error("Error reading frame from camera")
                    if not self.simulation_mode:
                        # Switch to simulation mode
                        logger.info("Switching to simulation mode")
                        self.simulation_mode = True
                        continue
                    break
                
                # Add frame to queue if not full
                if not self.frame_queue.full():
                    self.frame_queue.put(frame)
                
                # Get results if available
                try:
                    result = self.result_queue.get_nowait()
                    self._publish_results(result)
                except queue.Empty:
                    pass
                
                # Display frame
                cv2.imshow('Space Monitoring', frame)
                
                # Break on 'q' press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("Received quit signal")
                    break
            
            self.stop()
            
        except Exception as e:
            logger.error(f"Error in detection service: {str(e)}")
            self.stop()
    
    def _process_frames(self):
        """Process frames in a separate thread."""
        logger.info("Frame processing thread started")
        while self.is_running:
            try:
                frame = self.frame_queue.get(timeout=1)
                annotated_frame, tracking_info = self.detector.detect_and_track(frame)
                
                if not self.result_queue.full():
                    self.result_queue.put((annotated_frame, tracking_info))
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing frame: {str(e)}")
                continue
    
    def _publish_results(self, result):
        """Publish detection results to Redis."""
        try:
            annotated_frame, tracking_info = result
            
            # Convert frame to JPEG
            _, jpeg = cv2.imencode('.jpg', annotated_frame)
            
            # Ensure tracking_info is JSON serializable (convert any bytes objects)
            serializable_tracking = self._make_serializable(tracking_info)
            
            # Prepare data for publishing
            data = {
                'timestamp': datetime.now().isoformat(),
                'frame': base64.b64encode(jpeg.tobytes()).decode('utf-8'),
                'tracking_info': serializable_tracking
            }
            
            # Publish to Redis
            self.redis_client.publish('detection_results', json.dumps(data))
            
        except Exception as e:
            logger.error(f"Error publishing results: {str(e)}")
    
    def _make_serializable(self, obj):
        """Convert an object with potential bytes to JSON serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, bytes):
            return base64.b64encode(obj).decode('utf-8')
        elif isinstance(obj, (np.ndarray, np.generic)):
            # Handle numpy arrays and types
            if np.issubdtype(obj.dtype, np.number):
                return obj.tolist()
            else:
                return str(obj)
        elif isinstance(obj, (int, float, str, bool, type(None))):
            # These types are already JSON serializable
            return obj
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        else:
            # Convert anything else to string
            return str(obj)
    
    def stop(self):
        """Stop the detection service."""
        logger.info("Stopping detection service...")
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join()
        if hasattr(self, 'cap') and self.cap and not self.simulation_mode:
            self.cap.release()
        cv2.destroyAllWindows()
        if self.redis_client:
            self.redis_client.close()
        logger.info("Detection service stopped")

    def _initialize_camera(self):
        """Initialize the camera."""
        try:
            camera_config = self.config['cameras'][0]  # Use the first camera for now
            logger.info(f"Initializing camera: {camera_config}")
            
            # Use the PersonDetector's camera initialization method
            self.detector._initialize_camera(camera_config)
            self.camera = self.detector.cap
            
            if not self.camera or not self.camera.isOpened():
                logger.error("Failed to initialize camera")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error initializing camera: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        service = DetectionService()
        service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        service.stop()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        if 'service' in locals():
            service.stop() 