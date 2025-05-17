import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
from typing import List, Dict, Tuple
import yaml
import os
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('PersonDetector')

class PersonDetector:
    def __init__(self, config_path: str = "config/config.yaml"):
        try:
            # Load configuration
            logger.info("Loading configuration...")
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            # Initialize YOLO model
            logger.info("Loading YOLO model...")
            model_path = self.config['detection']['model']
            if not os.path.exists(model_path):
                logger.info(f"Model not found at {model_path}, downloading...")
            self.model = YOLO(model_path)
            
            # Initialize tracker
            logger.info("Initializing tracker...")
            self.tracker = sv.ByteTrack(
                track_activation_threshold=self.config['detection']['confidence_threshold'],
                lost_track_buffer=self.config['detection']['tracking']['max_age'],
                minimum_matching_threshold=self.config['detection']['tracking']['iou_threshold']
            )
            
            # Initialize zone polygons
            logger.info("Initializing zones...")
            self.zones = self._initialize_zones()
            
            # Initialize tracking state
            self.tracked_objects = {}
            self.zone_occupancy = {zone['name']: [] for zone in self._flatten_zones()}
            
            logger.info("Person detector initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing person detector: {str(e)}")
            raise
    
    def _initialize_zones(self) -> Dict:
        """Initialize zone polygons from configuration."""
        try:
            zones = {}
            for zone_type, zone_list in self.config['zones'].items():
                zones[zone_type] = []
                for zone in zone_list:
                    polygon = np.array(zone['coordinates'], dtype=np.int32)
                    zones[zone_type].append({
                        'name': zone['name'],
                        'polygon': polygon,
                        'type': zone['type'],
                        'max_capacity': zone.get('max_capacity', None)
                    })
            return zones
        except Exception as e:
            logger.error(f"Error initializing zones: {str(e)}")
            raise
    
    def _flatten_zones(self) -> List[Dict]:
        """Flatten zones dictionary into a list."""
        return [zone for zone_list in self.zones.values() for zone in zone_list]
    
    def detect_and_track(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        Detect and track people in the frame.
        Returns the annotated frame and tracking information.
        """
        try:
            # Run YOLO detection
            results = self.model(frame, verbose=False)[0]
            
            # Try different methods to create Detections object based on supervision version
            try:
                # First try from_ultralytics (newer versions)
                detections = sv.Detections.from_ultralytics(results)
            except (AttributeError, TypeError) as e:
                logger.warning(f"from_ultralytics failed: {str(e)}")
                try:
                    # Fallback to from_yolov8 (older versions)
                    detections = sv.Detections.from_yolov8(results)
                except (AttributeError, TypeError) as e:
                    logger.warning(f"from_yolov8 failed: {str(e)}")
                    # Manual conversion as last resort
                    logger.info("Using manual detection conversion")
                    boxes = results.boxes.xyxy.cpu().numpy()
                    scores = results.boxes.conf.cpu().numpy()
                    class_ids = results.boxes.cls.cpu().numpy().astype(int)
                    
                    detections = sv.Detections(
                        xyxy=boxes,
                        confidence=scores,
                        class_id=class_ids
                    )
            
            # Filter for person class (class 0 in COCO dataset)
            detections = detections[detections.class_id == 0]
            
            # Track objects
            detections = self.tracker.update_with_detections(detections)
            
            # Update tracking state
            self._update_tracking_state(detections)
            
            # Draw annotations
            annotated_frame = self._draw_annotations(frame, detections)
            
            return annotated_frame, self._get_tracking_info()
            
        except Exception as e:
            logger.error(f"Error in detect_and_track: {str(e)}")
            return frame, self._get_tracking_info()
    
    def _update_tracking_state(self, detections: sv.Detections):
        """Update the tracking state with new detections."""
        try:
            current_tracks = set()
            
            for detection in detections:
                track_id = detection.tracker_id
                if track_id is None:
                    continue
                    
                current_tracks.add(track_id)
                bbox = detection.xyxy[0]
                center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                
                # Update tracked object
                if track_id not in self.tracked_objects:
                    self.tracked_objects[track_id] = {
                        'current_zone': None,
                        'entry_time': None,
                        'last_seen': None
                    }
                
                # Check zone occupancy
                current_zone = self._get_zone_at_point(center)
                if current_zone != self.tracked_objects[track_id]['current_zone']:
                    self._handle_zone_change(track_id, current_zone)
                
                self.tracked_objects[track_id]['last_seen'] = center
            
            # Remove stale tracks
            stale_tracks = set(self.tracked_objects.keys()) - current_tracks
            for track_id in stale_tracks:
                del self.tracked_objects[track_id]
                
        except Exception as e:
            logger.error(f"Error updating tracking state: {str(e)}")
    
    def _get_zone_at_point(self, point: Tuple[float, float]) -> str:
        """Determine which zone a point is in."""
        try:
            for zone in self._flatten_zones():
                if cv2.pointPolygonTest(zone['polygon'], point, False) >= 0:
                    return zone['name']
            return None
        except Exception as e:
            logger.error(f"Error getting zone at point: {str(e)}")
            return None
    
    def _handle_zone_change(self, track_id: int, new_zone: str):
        """Handle zone changes for tracked objects."""
        try:
            old_zone = self.tracked_objects[track_id]['current_zone']
            
            # Remove from old zone
            if old_zone and track_id in self.zone_occupancy[old_zone]:
                self.zone_occupancy[old_zone].remove(track_id)
            
            # Add to new zone
            if new_zone:
                self.zone_occupancy[new_zone].append(track_id)
                self.tracked_objects[track_id]['entry_time'] = cv2.getTickCount() / cv2.getTickFrequency()
            
            self.tracked_objects[track_id]['current_zone'] = new_zone
            
        except Exception as e:
            logger.error(f"Error handling zone change: {str(e)}")
    
    def _draw_annotations(self, frame: np.ndarray, detections: sv.Detections) -> np.ndarray:
        """Draw annotations on the frame."""
        try:
            # Draw zones
            for zone in self._flatten_zones():
                cv2.polylines(frame, [zone['polygon']], True, (0, 255, 0), 2)
                cv2.putText(frame, zone['name'], 
                           (zone['polygon'][0][0], zone['polygon'][0][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Draw detections
            box_annotator = sv.BoxAnnotator()
            frame = box_annotator.annotate(frame, detections)
            
            return frame
            
        except Exception as e:
            logger.error(f"Error drawing annotations: {str(e)}")
            return frame
    
    def _get_tracking_info(self) -> Dict:
        """Get current tracking information."""
        return {
            'tracked_objects': self.tracked_objects,
            'zone_occupancy': self.zone_occupancy
        }

    def _initialize_camera(self, camera_config):
        """Initialize the camera."""
        try:
            # Get camera source - could be an index (0, 1, etc.) or URL string
            source = camera_config.get("source", 0)
            
            # Handle different source types
            if isinstance(source, str) and (source.startswith('http') or source.startswith('rtsp')):
                # This is a URL (IP camera, RTSP stream, etc.)
                logger.info(f"Initializing IP camera from: {source}")
                self.cap = cv2.VideoCapture(source)
            elif isinstance(source, str) and source.isdigit():
                # This is a numeric string, convert to int
                logger.info(f"Initializing webcam from index: {int(source)}")
                self.cap = cv2.VideoCapture(int(source))
            else:
                # This is a direct index (0 = default webcam)
                logger.info(f"Initializing webcam from index: {source}")
                self.cap = cv2.VideoCapture(source)
                
            # Set resolution if specified
            if "resolution" in camera_config:
                width, height = camera_config["resolution"]
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
            # Set FPS if specified
            if "fps" in camera_config:
                self.cap.set(cv2.CAP_PROP_FPS, camera_config["fps"])
                
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera: {source}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error initializing camera: {str(e)}")
            return False 