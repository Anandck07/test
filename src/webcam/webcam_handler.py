import cv2
import time
import os
import datetime
import threading
import base64
import numpy as np
from io import BytesIO
from PIL import Image
import random
import math

class WebcamHandler:
    def __init__(self, webcam_url=None, recording_path="recordings"):
        """Initialize webcam handler with URL."""
        self.webcam_url = webcam_url
        self.recording_path = recording_path
        self.cap = None
        self.is_recording = False
        self.is_monitoring = False
        self.recording_thread = None
        self.monitoring_thread = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.employee_data = {}
        self.is_demo_mode = webcam_url is None
        
        # Analytics data
        self.zone_data = {
            "desk_areas": {"capacity": 10, "current": 0, "max_today": 0},
            "meeting_rooms": {"capacity": 8, "current": 0, "max_today": 0},
            "break_areas": {"capacity": 6, "current": 0, "max_today": 0}
        }
        
        # Productivity metrics
        self.productivity_metrics = {
            "productive_hours": {},
            "meeting_hours": {},
            "break_hours": {},
            "overall_utilization": 0.0
        }
        
        # Historical data
        self.historical_data = []
        
        # Demo mode variables
        self.demo_frame_count = 0
        self.demo_people = {}  # People in the demo simulation with movement patterns
        self.demo_start_time = datetime.datetime.now()
        
        # Create recordings directory if it doesn't exist
        os.makedirs(recording_path, exist_ok=True)
        
        # Start analytics thread
        self.analytics_thread = threading.Thread(target=self._update_analytics_thread)
        self.analytics_thread.daemon = True
        self.analytics_thread.start()
        
        # Start historical data generation thread for demo mode
        if self.is_demo_mode:
            self._initialize_demo_people()
            self.historical_thread = threading.Thread(target=self._generate_historical_data_thread)
            self.historical_thread.daemon = True
            self.historical_thread.start()
    
    def _initialize_demo_people(self):
        """Initialize simulated people for the demo."""
        # Create 5-8 simulated people
        person_count = random.randint(5, 8)
        for i in range(person_count):
            person_id = f"person_{i+1}"
            
            # Assign initial zone
            zone_type = random.choice(["desk", "meeting", "break"])
            
            # Assign a predetermined behavior pattern
            behavior = random.choice([
                "mostly_desk",      # 70% desk, 20% meeting, 10% break
                "desk_meeting_mix", # 50% desk, 40% meeting, 10% break
                "frequent_breaks",  # 50% desk, 20% meeting, 30% break
                "meeting_heavy"     # 30% desk, 60% meeting, 10% break
            ])
            
            # Create starting position based on zone
            if zone_type == "desk":
                x = random.randint(50, 300)
                y = random.randint(50, 200)
            elif zone_type == "meeting":
                x = random.randint(350, 550)
                y = random.randint(50, 200)
            else:  # break
                x = random.randint(150, 450)
                y = random.randint(250, 400)
            
            # Add the person to the demo
            self.demo_people[person_id] = {
                "id": person_id,
                "first_seen": datetime.datetime.now(),
                "last_seen": datetime.datetime.now(),
                "zone": zone_type,
                "behavior": behavior,
                "activity_level": np.random.uniform(0.5, 0.9),
                "position": (x, y),
                "target_position": (x, y),
                "productive_minutes": random.randint(20, 120),
                "meeting_minutes": random.randint(10, 60),
                "break_minutes": random.randint(5, 30),
                "time_in_current_zone": random.randint(1, 30),
                "name": f"Employee {i+1}",
                "next_zone_change": time.time() + random.randint(10, 60)
            }
            
            # Update employee data structure to match
            self.employee_data[person_id] = self.demo_people[person_id].copy()
    
    def connect(self):
        """Connect to webcam."""
        # If in demo mode, don't attempt to connect to a real webcam
        if self.is_demo_mode:
            print("Running in demo mode - no webcam connection needed")
            return True
            
        if self.webcam_url:
            try:
                self.cap = cv2.VideoCapture(self.webcam_url)
                if not self.cap.isOpened():
                    print(f"Failed to open webcam: {self.webcam_url}")
                    self.is_demo_mode = True
                    self._initialize_demo_people()
                    return True  # Return True to allow fallback to demo mode
                return True
            except Exception as e:
                print(f"Error connecting to webcam: {e}")
                self.is_demo_mode = True
                self._initialize_demo_people()
                return True  # Return True to allow fallback to demo mode
        else:
            # Try to connect to default camera
            try:
                self.cap = cv2.VideoCapture(0)
                if not self.cap.isOpened():
                    print("Failed to open default webcam")
                    self.is_demo_mode = True
                    self._initialize_demo_people()
                    return True  # Return True to allow fallback to demo mode
                return True
            except Exception as e:
                print(f"Error connecting to default webcam: {e}")
                self.is_demo_mode = True
                self._initialize_demo_people()
                return True  # Return True to allow fallback to demo mode
    
    def disconnect(self):
        """Disconnect from webcam."""
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def get_frame(self):
        """Get current frame from webcam."""
        # If in demo mode, generate a demo frame
        if self.is_demo_mode:
            return self._generate_demo_frame()
            
        if not self.cap or not self.cap.isOpened():
            if not self.connect():
                # If connection failed but we're in demo mode, generate a demo frame
                if self.is_demo_mode:
                    return self._generate_demo_frame()
                return None
        
        try:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to get frame from webcam, falling back to demo mode")
                self.is_demo_mode = True
                return self._generate_demo_frame()
            
            with self.frame_lock:
                self.current_frame = frame
            
            return frame
        except Exception as e:
            print(f"Error getting frame: {e}, falling back to demo mode")
            self.is_demo_mode = True
            return self._generate_demo_frame()
    
    def _generate_demo_frame(self):
        """Generate a demo frame for simulation with enhanced visualization."""
        # Update frame count
        self.demo_frame_count += 1
        
        # Update simulated people positions and zones
        self._update_demo_people()
        
        # Create a simple floor plan 
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (35, 35, 35)  # Dark gray background
        
        # Add office layout - desk areas (green zone)
        cv2.rectangle(img, (30, 30), (300, 220), (0, 100, 0), 2)
        cv2.putText(img, "DESK AREA", (120, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
        
        # Draw individual desks
        for i in range(5):
            desk_x = 50 + i * 50
            cv2.rectangle(img, (desk_x, 60), (desk_x + 40, 100), (0, 80, 0), 1)
            cv2.rectangle(img, (desk_x, 140), (desk_x + 40, 180), (0, 80, 0), 1)
        
        # Meeting room area (blue zone)
        cv2.rectangle(img, (340, 30), (600, 220), (100, 50, 0), 2)
        cv2.putText(img, "MEETING ROOMS", (400, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 100, 0), 2)
        
        # Draw meeting rooms
        cv2.rectangle(img, (360, 60), (460, 140), (100, 40, 0), 1)
        cv2.rectangle(img, (480, 60), (580, 140), (100, 40, 0), 1)
        
        # Break area (orange zone)
        cv2.rectangle(img, (150, 250), (450, 430), (0, 50, 100), 2)
        cv2.putText(img, "BREAK AREA", (270, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 100, 200), 2)
        
        # Draw break area furniture
        cv2.circle(img, (250, 350), 30, (0, 40, 80), 1)  # Table
        cv2.rectangle(img, (350, 330), (420, 370), (0, 40, 80), 1)  # Couch
        
        # Add current time
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, timestamp, (20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add simulation indicator
        cv2.putText(img, "SIMULATION MODE", (450, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)
        
        # Get zone data for visualization
        desk_util = self.zone_data["desk_areas"]["current"] / max(1, self.zone_data["desk_areas"]["capacity"]) * 100
        meeting_util = self.zone_data["meeting_rooms"]["current"] / max(1, self.zone_data["meeting_rooms"]["capacity"]) * 100
        break_util = self.zone_data["break_areas"]["current"] / max(1, self.zone_data["break_areas"]["capacity"]) * 100
        
        # Add zone utilization text
        cv2.putText(img, f"Desk Utilization: {desk_util:.1f}%", (20, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)
        cv2.putText(img, f"Meeting Room: {meeting_util:.1f}%", (230, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 100, 0), 1)
        cv2.putText(img, f"Break Area: {break_util:.1f}%", (430, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 200), 1)
        
        # Draw people on the map
        for person_id, data in self.demo_people.items():
            x, y = data["position"]
            
            # Color based on zone
            if data["zone"] == "desk":
                color = (0, 255, 0)  # Green for desk
            elif data["zone"] == "meeting":
                color = (0, 165, 255)  # Orange for meeting
            else:
                color = (255, 0, 0)  # Red for break
            
            # Draw the person as a circle with their ID
            cv2.circle(img, (int(x), int(y)), 10, color, -1)
            cv2.putText(img, data["id"][-1], (int(x)-3, int(y)+3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            
            # Add activity indicator - pulsing effect based on activity level
            pulse_size = 13 + int(3 * math.sin(self.demo_frame_count * 0.1) * data["activity_level"])
            cv2.circle(img, (int(x), int(y)), pulse_size, color, 1)
        
        with self.frame_lock:
            self.current_frame = img
        
        return img
    
    def _update_demo_people(self):
        """Update simulated people's positions and states for the demo."""
        current_time = time.time()
        
        for person_id, data in self.demo_people.items():
            # Check if it's time to change zones
            if current_time > data["next_zone_change"]:
                # Decide next zone based on behavior pattern
                behavior = data["behavior"]
                rand = random.random()
                
                if behavior == "mostly_desk":
                    if rand < 0.7:
                        next_zone = "desk"
                    elif rand < 0.9:
                        next_zone = "meeting"
                    else:
                        next_zone = "break"
                elif behavior == "desk_meeting_mix":
                    if rand < 0.5:
                        next_zone = "desk"
                    elif rand < 0.9:
                        next_zone = "meeting"
                    else:
                        next_zone = "break"
                elif behavior == "frequent_breaks":
                    if rand < 0.5:
                        next_zone = "desk"
                    elif rand < 0.7:
                        next_zone = "meeting"
                    else:
                        next_zone = "break"
                elif behavior == "meeting_heavy":
                    if rand < 0.3:
                        next_zone = "desk"
                    elif rand < 0.9:
                        next_zone = "meeting"
                    else:
                        next_zone = "break"
                else:
                    next_zone = random.choice(["desk", "meeting", "break"])
                
                # Assign new position target based on zone
                if next_zone == "desk":
                    target_x = random.randint(50, 280)
                    target_y = random.randint(70, 200)
                elif next_zone == "meeting":
                    target_x = random.randint(360, 580)
                    target_y = random.randint(70, 200)
                else:  # break
                    target_x = random.randint(180, 420)
                    target_y = random.randint(280, 400)
                
                # Update person data
                data["zone"] = next_zone
                data["target_position"] = (target_x, target_y)
                data["next_zone_change"] = current_time + random.randint(30, 120)  # 30s to 2min
                data["time_in_current_zone"] = 0
                
                # Update activity level when changing zones
                if next_zone == "desk":
                    data["activity_level"] = min(0.9, data["activity_level"] + random.uniform(0.1, 0.2))
                elif next_zone == "meeting":
                    data["activity_level"] = min(0.9, max(0.4, data["activity_level"] + random.uniform(-0.1, 0.1)))
                else:  # break
                    data["activity_level"] = max(0.2, data["activity_level"] - random.uniform(0.1, 0.3))
            
            # Update position - move toward target
            curr_x, curr_y = data["position"]
            target_x, target_y = data["target_position"]
            
            # Calculate movement (with some randomness)
            dx = (target_x - curr_x) * 0.05 + random.uniform(-1, 1)
            dy = (target_y - curr_y) * 0.05 + random.uniform(-1, 1)
            
            # Update position
            new_x = curr_x + dx
            new_y = curr_y + dy
            
            # Keep within boundaries
            new_x = max(20, min(620, new_x))
            new_y = max(20, min(460, new_y))
            
            data["position"] = (new_x, new_y)
            
            # Update time in current zone
            data["time_in_current_zone"] += 0.1  # Assuming this is called ~10 times per second
            
            # Increment time counters based on zone
            if data["zone"] == "desk":
                data["productive_minutes"] += 0.1 / 6  # Convert to minutes (0.1/6 = 1 second)
            elif data["zone"] == "meeting":
                data["meeting_minutes"] += 0.1 / 6
            elif data["zone"] == "break":
                data["break_minutes"] += 0.1 / 6
            
            # Update last seen time
            data["last_seen"] = datetime.datetime.now()
            
            # Occasionally vary activity level slightly
            if random.random() < 0.05:
                activity_change = random.uniform(-0.05, 0.05)
                data["activity_level"] = max(0.1, min(0.9, data["activity_level"] + activity_change))
            
            # Sync with employee_data
            self.employee_data[person_id] = data.copy()
        
        # Update zone metrics
        self._update_zone_metrics()
    
    def get_encoded_frame(self):
        """Get frame encoded as JPEG base64 string."""
        frame = self.get_frame()
        if frame is None:
            # Generate a demo frame as fallback
            frame = self._generate_demo_frame()
        
        # Convert frame to JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        
        # Convert to base64
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        
        return jpg_as_text
    
    def get_pil_image(self):
        """Get frame as PIL Image."""
        frame = self.get_frame()
        if frame is None:
            # Generate a demo frame as fallback
            frame = self._generate_demo_frame()
        
        # Convert from BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        pil_image = Image.fromarray(rgb_frame)
        
        return pil_image
    
    def start_recording(self, duration=None, filename=None):
        """Start recording video from webcam."""
        if self.is_recording:
            print("Already recording")
            return False
        
        if not self.cap and not self.is_demo_mode:
            if not self.connect():
                print("Failed to connect to webcam")
                return False
        
        # Get webcam properties - use defaults for demo mode
        if self.is_demo_mode:
            width = 640
            height = 480
            fps = 30
        else:
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            if fps == 0:
                fps = 30  # Default if not available
        
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.mp4"
        
        # Create full path
        filepath = os.path.join(self.recording_path, filename)
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
        
        # Set recording flag
        self.is_recording = True
        self.recording_filepath = filepath
        
        # Start recording thread
        self.recording_thread = threading.Thread(target=self._record_thread, args=(duration,))
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        return True
    
    def stop_recording(self):
        """Stop recording video."""
        if not self.is_recording:
            return False
        
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=5)
        
        if hasattr(self, 'writer'):
            self.writer.release()
        
        return self.recording_filepath
    
    def _record_thread(self, duration=None):
        """Thread function for recording."""
        start_time = time.time()
        
        while self.is_recording:
            if duration and time.time() - start_time > duration:
                break
            
            # Get current frame
            frame = self.get_frame()  # This will now handle demo mode internally
            
            if frame is not None:
                self.writer.write(frame)
            
            # Sleep to limit CPU usage
            time.sleep(0.01)
        
        # Stop recording
        self.stop_recording()
    
    def start_employee_monitoring(self):
        """Start monitoring employees in webcam feed."""
        if self.is_monitoring:
            return False
        
        if not self.cap and not self.is_demo_mode:
            if not self.connect():
                print("Failed to connect to webcam")
                return False
        
        # Set monitoring flag
        self.is_monitoring = True
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitor_thread)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        return True
    
    def stop_employee_monitoring(self):
        """Stop monitoring employees."""
        if not self.is_monitoring:
            return False
        
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        return True
    
    def _monitor_thread(self):
        """Thread function for employee monitoring."""
        # In a real application, this would use face recognition and tracking
        # to detect and monitor employees
        
        while self.is_monitoring:
            # Get current frame
            frame = self.get_frame()  # This will now handle demo mode internally
            
            if frame is not None and not self.is_demo_mode:
                # Process frame to detect employees
                # This is a placeholder for actual employee detection logic
                # For demonstration, we'll just simulate detecting random people
                
                # Extract frame dimensions
                height, width = frame.shape[:2]
                
                # Simulate detecting 0-5 people
                person_count = np.random.randint(0, 6)
                
                # Generate random locations for people
                for i in range(person_count):
                    # Random position
                    x = np.random.randint(0, width)
                    y = np.random.randint(0, height)
                    
                    # Generate a random ID
                    person_id = f"person_{i+1}"
                    
                    # Assign to a random zone for demo
                    zone_type = random.choice(["desk", "meeting", "break"])
                    
                    # Update employee data
                    if person_id not in self.employee_data:
                        self.employee_data[person_id] = {
                            "id": person_id,
                            "first_seen": datetime.datetime.now(),
                            "last_seen": datetime.datetime.now(),
                            "position": (x, y),
                            "zone": zone_type,
                            "activity_level": np.random.uniform(0.3, 0.9),
                            "productive_minutes": 0,
                            "meeting_minutes": 0,
                            "break_minutes": 0
                        }
                    else:
                        # Update existing data
                        self.employee_data[person_id]["last_seen"] = datetime.datetime.now()
                        self.employee_data[person_id]["position"] = (x, y)
                        
                        # Randomly change zone sometimes
                        if random.random() < 0.05:
                            zone_type = random.choice(["desk", "meeting", "break"])
                            self.employee_data[person_id]["zone"] = zone_type
                        
                        # Update activity level with some fluctuation
                        activity_change = np.random.uniform(-0.1, 0.1)
                        new_activity = max(0.1, min(0.9, self.employee_data[person_id]["activity_level"] + activity_change))
                        self.employee_data[person_id]["activity_level"] = new_activity
                        
                        # Increment time counters based on zone
                        if zone_type == "desk":
                            self.employee_data[person_id]["productive_minutes"] += 0.5  # Adding half minute
                        elif zone_type == "meeting":
                            self.employee_data[person_id]["meeting_minutes"] += 0.5
                        elif zone_type == "break":
                            self.employee_data[person_id]["break_minutes"] += 0.5
            
            # Update zone utilization metrics
            self._update_zone_metrics()
            
            # Sleep to limit CPU usage
            time.sleep(0.5)
    
    def _update_zone_metrics(self):
        """Update metrics for zone utilization."""
        # Reset current counts
        for zone in self.zone_data:
            self.zone_data[zone]["current"] = 0
        
        # Count people in each zone
        for person_id, data in self.employee_data.items():
            zone = data.get("zone", "desk")
            
            if zone == "desk":
                self.zone_data["desk_areas"]["current"] += 1
            elif zone == "meeting":
                self.zone_data["meeting_rooms"]["current"] += 1
            elif zone == "break":
                self.zone_data["break_areas"]["current"] += 1
        
        # Update max values
        for zone in self.zone_data:
            if self.zone_data[zone]["current"] > self.zone_data[zone]["max_today"]:
                self.zone_data[zone]["max_today"] = self.zone_data[zone]["current"]
        
        # Calculate overall utilization
        total_capacity = sum(zone["capacity"] for zone in self.zone_data.values())
        total_current = sum(zone["current"] for zone in self.zone_data.values())
        
        if total_capacity > 0:
            self.productivity_metrics["overall_utilization"] = total_current / total_capacity
    
    def _update_analytics_thread(self):
        """Background thread to continuously update analytics."""
        while True:
            # Update productivity metrics
            self._update_productivity_metrics()
            
            # Update historical data
            if random.random() < 0.2:  # Increase frequency of historical data updates
                self._update_historical_data()
            
            # Sleep between updates
            time.sleep(5)
    
    def _update_productivity_metrics(self):
        """Update productivity metrics based on employee data."""
        # Reset metrics
        self.productivity_metrics["productive_hours"] = {}
        self.productivity_metrics["meeting_hours"] = {}
        self.productivity_metrics["break_hours"] = {}
        
        # Calculate metrics from employee data
        for person_id, data in self.employee_data.items():
            # Convert minutes to hours
            productive_hours = data.get("productive_minutes", 0) / 60.0
            meeting_hours = data.get("meeting_minutes", 0) / 60.0
            break_hours = data.get("break_minutes", 0) / 60.0
            
            self.productivity_metrics["productive_hours"][person_id] = round(productive_hours, 2)
            self.productivity_metrics["meeting_hours"][person_id] = round(meeting_hours, 2)
            self.productivity_metrics["break_hours"][person_id] = round(break_hours, 2)
    
    def _update_historical_data(self):
        """Update historical data for analytics."""
        # Create a snapshot of current metrics
        snapshot = {
            "timestamp": datetime.datetime.now().isoformat(),
            "desk_occupancy_rate": self.zone_data["desk_areas"]["current"] / max(1, self.zone_data["desk_areas"]["capacity"]),
            "meeting_room_utilization": self.zone_data["meeting_rooms"]["current"] / max(1, self.zone_data["meeting_rooms"]["capacity"]),
            "break_area_utilization": self.zone_data["break_areas"]["current"] / max(1, self.zone_data["break_areas"]["capacity"]),
            "overall_utilization": self.productivity_metrics["overall_utilization"],
            "employee_count": len(self.employee_data),
            "active_employees": sum(1 for data in self.employee_data.values() if data.get("activity_level", 0) > 0.3),
            "total_productive_hours": sum(self.productivity_metrics["productive_hours"].values()),
            "total_meeting_hours": sum(self.productivity_metrics["meeting_hours"].values()),
            "total_break_hours": sum(self.productivity_metrics["break_hours"].values())
        }
        
        self.historical_data.append(snapshot)
        
        # Limit the size of historical data to prevent memory issues
        if len(self.historical_data) > 1000:
            self.historical_data = self.historical_data[-1000:]
    
    def _generate_historical_data_thread(self):
        """Generate realistic historical data for demo mode."""
        # Generate data for the past few "days" (accelerated timeline)
        
        # Wait a bit before starting to generate historical data
        time.sleep(10)
        
        # Generate 7 days of historical data
        for day in range(7):
            day_date = datetime.datetime.now() - datetime.timedelta(days=7-day)
            
            # Generate data for each hour of the workday (8 AM - 6 PM)
            for hour in range(8, 19):
                # Create base time for this hour
                base_time = day_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                
                # Generate data for each 15-minute interval
                for minute in [0, 15, 30, 45]:
                    timestamp = base_time + datetime.timedelta(minutes=minute)
                    
                    # Generate data based on realistic patterns
                    # Morning: Gradual increase in desk occupancy
                    # Mid-day: Peak meeting room usage, lower desk occupancy
                    # Afternoon: Variable patterns, gradual decrease toward end of day
                    
                    # Set occupancy rates based on time of day and day of week
                    if day_date.weekday() >= 5:  # Weekend
                        desk_occupancy = random.uniform(0.05, 0.2)
                        meeting_occupancy = random.uniform(0, 0.1)
                        break_occupancy = random.uniform(0, 0.05)
                        employee_count = random.randint(1, 3)
                    else:  # Weekday
                        # Morning ramp-up
                        if hour < 10:
                            desk_occupancy = random.uniform(0.3, 0.6) * (hour - 7) / 3
                            meeting_occupancy = random.uniform(0.1, 0.3) * (hour - 7) / 3
                            break_occupancy = random.uniform(0.1, 0.2)
                        # Mid-day
                        elif hour < 14:
                            desk_occupancy = random.uniform(0.6, 0.9)
                            # Lunch hour
                            if hour == 12:
                                desk_occupancy *= 0.7
                                break_occupancy = random.uniform(0.5, 0.9)
                                meeting_occupancy = random.uniform(0.2, 0.4)
                            else:
                                meeting_occupancy = random.uniform(0.4, 0.8)
                                break_occupancy = random.uniform(0.2, 0.4)
                        # Afternoon
                        else:
                            desk_occupancy = random.uniform(0.5, 0.8) * (19 - hour) / 5
                            meeting_occupancy = random.uniform(0.3, 0.6) * (19 - hour) / 5
                            break_occupancy = random.uniform(0.1, 0.3)
                        
                        employee_count = random.randint(5, 12)
                    
                    active_employees = int(employee_count * random.uniform(0.7, 1.0))
                    
                    # Calculate hours based on employee count and time
                    total_hours_factor = employee_count * (timestamp - day_date.replace(hour=8, minute=0, second=0)).total_seconds() / 3600
                    total_productive_hours = total_hours_factor * random.uniform(0.5, 0.8)
                    total_meeting_hours = total_hours_factor * random.uniform(0.1, 0.3)
                    total_break_hours = total_hours_factor * random.uniform(0.05, 0.15)
                    
                    # Create historical data entry
                    historical_entry = {
                        "timestamp": timestamp.isoformat(),
                        "desk_occupancy_rate": desk_occupancy,
                        "meeting_room_utilization": meeting_occupancy,
                        "break_area_utilization": break_occupancy,
                        "overall_utilization": (desk_occupancy + meeting_occupancy + break_occupancy) / 3,
                        "employee_count": employee_count,
                        "active_employees": active_employees,
                        "total_productive_hours": total_productive_hours,
                        "total_meeting_hours": total_meeting_hours,
                        "total_break_hours": total_break_hours
                    }
                    
                    # Add to historical data
                    self.historical_data.append(historical_entry)
            
            # Sort historical data by timestamp
            self.historical_data.sort(key=lambda x: x["timestamp"])
    
    def get_employee_data(self):
        """Get current employee monitoring data."""
        return self.employee_data
    
    def get_zone_data(self):
        """Get zone utilization data."""
        return self.zone_data
    
    def get_productivity_metrics(self):
        """Get productivity metrics."""
        return self.productivity_metrics
    
    def get_historical_data(self):
        """Get historical data for analytics."""
        return self.historical_data


# Function to create a demo handler that simulates webcam functionality
def create_demo_handler():
    """Create a demo webcam handler that simulates functionality."""
    handler = WebcamHandler()
    # Set demo mode explicitly
    handler.is_demo_mode = True
    return handler 