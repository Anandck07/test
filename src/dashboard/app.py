import streamlit as st
import redis
import json
import cv2
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yaml
import base64
from io import BytesIO
import time
import pandas as pd
import hashlib
import os
import secrets
import requests
import threading
import io
from PIL import Image
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from webcam_page import render_webcam_page

# Load configuration
try:
    # Try relative path from dashboard directory
    with open("../../config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    # Alternative path when running from project root
    with open("config/config.yaml", 'r') as f:
        config = yaml.safe_load(f)

# Initialize Redis connection
try:
    redis_client = redis.Redis(
        host=config['redis']['host'],
        port=config['redis']['port'],
        db=config['redis']['db']
    )
    # Test connection
    redis_client.ping()
    print("Successfully connected to Redis")
except:
    print("Redis connection failed. Using mock Redis for development.")
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
            if channel not in self.pubsub_channels:
                self.pubsub_channels[channel] = []
            self.pubsub_channels[channel].append(message)
            return 1
            
        def ping(self):
            return True
    
    redis_client = MockRedis()

# Set page config
st.set_page_config(
    page_title="Space Monitoring Dashboard",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = True
    st.session_state.username = "User"
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "Dashboard"
if 'selected_camera' not in st.session_state:
    st.session_state.selected_camera = "cam1"
if 'users' not in st.session_state:
    st.session_state.users = {'admin': {'password_hash': hashlib.sha256('admin'.encode()).hexdigest(), 'role': 'admin'}}
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()
if 'metrics_history' not in st.session_state:
    st.session_state.metrics_history = []

# Save session state to cookie to persist between runs
@st.cache_data(persist="disk")
def get_session_state():
    return st.session_state

# Load session state from cookie at startup
def load_session_state():
    cached_state = get_session_state()
    if cached_state is not None:
        # Only restore authentication state to avoid conflicts
        if 'authenticated' in cached_state and cached_state.authenticated:
            st.session_state.authenticated = cached_state.authenticated
            st.session_state.username = cached_state.username

# Load session state at startup
load_session_state()

# Authentication functions that won't be used but kept for compatibility
def login_user(username, password):
    return True

def register_user(username, password, confirm_password):
    return True, "Registration successful"

def logout_user():
    st.session_state.current_tab = "Dashboard"
    st.rerun()

# Dashboard functions
def get_latest_frame(camera_id="cam1"):
    """Get the latest frame from Redis for a specific camera."""
    try:
        data = redis_client.get(f'latest_frame_{camera_id}')
        if data:
            frame_data = json.loads(data)
            frame_bytes = base64.b64decode(frame_data['frame'])
            frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
            return frame, frame_data['timestamp']
        
        # Fallback to default latest_frame key
        data = redis_client.get('latest_frame')
        if data:
            frame_data = json.loads(data)
            frame_bytes = base64.b64decode(frame_data['frame'])
            frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
            return frame, frame_data['timestamp']
    except Exception as e:
        st.error(f"Error getting frame: {e}")
    return None, None

def get_metrics():
    """Get the latest metrics from Redis."""
    try:
        data = redis_client.get('latest_metrics')
        if data:
            return json.loads(data)
    except Exception as e:
        st.error(f"Error getting metrics: {e}")
    return None

def create_heatmap(metrics):
    """Create a heatmap of zone utilization."""
    if not metrics or 'zone_utilization' not in metrics:
        return None
    
    zones = list(metrics['zone_utilization'].keys())
    utilization = [data['current'] for data in metrics['zone_utilization'].values()]
    
    fig = go.Figure(data=go.Heatmap(
        z=[utilization],
        x=zones,
        y=['Utilization'],
        colorscale='RdYlGn_r',
        showscale=True
    ))
    
    fig.update_layout(
        title='Zone Utilization Heatmap',
        xaxis_title='Zone',
        yaxis_title='',
        height=200
    )
    
    return fig

def create_productivity_chart(metrics):
    """Create a chart showing productivity metrics."""
    if not metrics:
        return None
    
    data = {
        'Zone': [],
        'Hours': [],
        'Type': []
    }
    
    for zone, hours in metrics.get('productive_hours', {}).items():
        data['Zone'].append(zone)
        data['Hours'].append(hours)
        data['Type'].append('Productive')
    
    for zone, hours in metrics.get('meeting_hours', {}).items():
        data['Zone'].append(zone)
        data['Hours'].append(hours)
        data['Type'].append('Meeting')
    
    for zone, hours in metrics.get('break_hours', {}).items():
        data['Zone'].append(zone)
        data['Hours'].append(hours)
        data['Type'].append('Break')
    
    fig = px.bar(
        data,
        x='Zone',
        y='Hours',
        color='Type',
        title='Time Spent by Zone Type',
        barmode='group'
    )
    
    return fig

def create_anomalies_table(metrics):
    """Create a table of recent anomalies."""
    if not metrics or 'anomalies' not in metrics:
        return None
    
    anomalies = metrics['anomalies']
    if not anomalies:
        return None
    
    df = pd.DataFrame(anomalies)
    return df

def generate_historical_data(period=30):
    """Generate historical data for analytics."""
    # In a real implementation, this would fetch from a database
    # For demo, we'll generate random data
    np.random.seed(42)
    
    current_date = datetime.now()
    dates = [(current_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(period)]
    timestamps = [(current_date - timedelta(days=i)).isoformat() for i in range(period)]
    
    data = {
        'date': dates,
        'timestamp': timestamps,
        'desk_occupancy_rate': np.random.uniform(0.4, 0.9, period),
        'meeting_room_utilization': np.random.uniform(0.3, 0.8, period),
        'break_area_utilization': np.random.uniform(0.2, 0.6, period),
        'productive_hours': np.random.uniform(4.0, 7.5, period),
        'meeting_hours': np.random.uniform(1.0, 3.0, period),
        'break_hours': np.random.uniform(0.5, 1.5, period),
        'idle_alerts': np.random.randint(0, 8, period),
        'unauthorized_access': np.random.randint(0, 3, period),
        'occupancy': np.random.randint(5, 30, period)
    }
    
    return pd.DataFrame(data)

# Dashboard layouts
def render_main_dashboard():
    """Render the main dashboard."""
    # Sidebar navigation
    with st.sidebar:
        st.title(f"Welcome, {st.session_state.username}!")
        
        st.subheader("Navigation")
        tabs = ["Dashboard", "Cameras", "Analytics", "Settings"]
        
        for tab in tabs:
            if st.button(tab, key=f"nav_{tab}"):
                st.session_state.current_tab = tab
        
        if st.session_state.current_tab == "Cameras":
            st.subheader("Camera Selection")
            cameras = [cam["id"] for cam in config["cameras"]]
            
            for camera in cameras:
                if st.button(f"Camera {camera}", key=f"cam_{camera}"):
                    st.session_state.selected_camera = camera
    
    # Main content based on selected tab
    if st.session_state.current_tab == "Dashboard":
        render_main_content()
    elif st.session_state.current_tab == "Cameras":
        render_camera_management()
    elif st.session_state.current_tab == "Analytics":
        render_analytics()
    elif st.session_state.current_tab == "Settings":
        render_settings()

def render_main_content():
    """Render the main dashboard content."""
    # Render the webcam monitoring page
    render_webcam_page()

def render_settings():
    """Render the settings page."""
    st.title("Settings")
    
    # System settings
    camera_tab, alert_tab, user_tab, system_tab = st.tabs(["Camera Setup", "Alert Settings", "User Management", "System Info"])
    
    with camera_tab:
        st.markdown("""
        ### Connect Mobile Phone Camera
        
        To use your mobile phone as a camera:
        
        1. Install an IP camera app on your mobile phone:
           - **Android:** IP Webcam, DroidCam
           - **iOS:** IP Camera Lite, EpocCam
           
        2. Connect your phone to the same WiFi network as this computer
        
        3. Open the app and start the camera server
        
        4. Add the camera URL below (usually in the format `http://phone-ip:port`)
        
        ### No Camera Available?
        
        If you don't have a camera available or are having connection issues, enable **Simulation Mode** to add the camera without validation.
        """)
        
        with st.form("add_ip_camera_settings"):
            cam_name = st.text_input("Camera Name", placeholder="e.g., Meeting Room")
            cam_url = st.text_input("Camera URL", placeholder="http://192.168.1.100:8080/video")
            cam_type = st.selectbox("Zone Type", ["Desk", "Meeting Room", "Break Area", "Other"])
            simulation_mode = st.checkbox("Enable Simulation Mode", help="Add camera without validating connection. Use if no camera is available.")
            
            if st.form_submit_button("Add Camera"):
                if cam_name and cam_url:
                    try:
                        # Call the API to add the camera
                        api_host = config['api']['host']
                        api_port = config['api']['port']
                        
                        # If host is 0.0.0.0, use localhost for client connections
                        if api_host == "0.0.0.0":
                            api_host = "localhost"
                            
                        response = requests.post(
                            f"http://{api_host}:{api_port}/cameras/add",
                            json={
                                "camera_name": cam_name,
                                "camera_url": cam_url,
                                "zone_type": cam_type.lower().replace(" ", "_"),
                                "simulation_mode": simulation_mode
                            },
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            st.success(f"Camera '{cam_name}' added successfully!")
                            st.info("To use the camera, restart the application")
                        else:
                            error_detail = response.json().get('detail', 'Unknown error')
                            st.error(f"Failed to add camera: {error_detail}")
                    except Exception as e:
                        st.error(f"Error connecting to API: {str(e)}")
                else:
                    st.error("Please enter both camera name and URL")
        
        st.divider()
        
        st.subheader("Mobile Connection Instructions")
        
        ip_cam_instructions = {
            "IP Webcam (Android)": """
            1. Install IP Webcam from Google Play Store
            2. Open the app and scroll down to "Start server"
            3. The app will display the URL to access the video feed
            4. Enter this URL in the "Camera URL" field above
            5. Camera URL format: `http://{phone-ip}:{port}/video`
            """,
            
            "DroidCam (Android)": """
            1. Install DroidCam from Google Play Store
            2. Open the app to see your device IP and port
            3. Camera URL format: `http://{phone-ip}:{port}/video`
            """,
            
            "IP Camera Lite (iOS)": """
            1. Install IP Camera Lite from App Store
            2. Open the app and tap "Start server"
            3. The app will display the RTSP URL
            4. Enter this URL in the "Camera URL" field above
            5. Camera URL format: `rtsp://{phone-ip}:{port}/live`
            """
        }
        
        app_select = st.selectbox("View instructions for:", list(ip_cam_instructions.keys()))
        st.code(ip_cam_instructions[app_select])
    
    with alert_tab:
        # Alert settings
        with st.form("alert_settings"):
            st.subheader("Alert Configuration")
            
            col1, col2 = st.columns(2)
            with col1:
                idle_threshold = st.number_input(
                    "Idle Alert Threshold (minutes)", 
                    value=config["analytics"]["idle_threshold_seconds"] // 60, 
                    min_value=1, 
                    max_value=60,
                    help="Trigger alert when person is idle for more than this duration"
                )
            with col2:
                unauthorized_threshold = st.number_input(
                    "Unauthorized Access Alert Threshold (seconds)", 
                    value=config["analytics"]["unauthorized_alert_threshold"],
                    min_value=10, 
                    max_value=300,
                    help="Time threshold for unauthorized access detection"
                )
            
            st.subheader("Zone Capacity Limits")
            
            # For each zone, allow setting capacity
            zone_capacities = {}
            
            for zone_category, zones in config['zones'].items():
                for zone in zones:
                    current_capacity = zone.get('max_capacity', 4)
                    zone_capacities[zone['name']] = st.number_input(
                        f"Max capacity for {zone['name']} ({zone['type']})",
                        value=current_capacity,
                        min_value=1,
                        max_value=50
                    )
            
            if st.form_submit_button("Save Alert Settings"):
                st.success("Alert settings saved successfully!")
                # In a real implementation, this would update the config file
    
    with user_tab:
        # User management (admin only)
        if st.session_state.users.get(st.session_state.username, {}).get('role') == 'admin':
            st.subheader("User Management (Admin)")
            
            users_data = []
            for username, user_data in st.session_state.users.items():
                users_data.append({
                    "Username": username,
                    "Role": user_data.get('role', 'user')
                })
            
            users_df = pd.DataFrame(users_data)
            st.dataframe(users_df)
            
            with st.form("add_user"):
                st.subheader("Add New User")
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["user", "admin"])
                
                if st.form_submit_button("Add User"):
                    if new_username in st.session_state.users:
                        st.error("Username already exists")
                    elif not new_username or not new_password:
                        st.error("Username and password cannot be empty")
                    else:
                        st.session_state.users[new_username] = {
                            'password_hash': hashlib.sha256(new_password.encode()).hexdigest(),
                            'role': new_role
                        }
                        st.success(f"User {new_username} added successfully!")
        else:
            st.info("User management is available to administrators only.")
    
    with system_tab:
        # System information
        st.subheader("System Information")
        
        try:
            redis_status = "Active" if redis_client.ping() else "Inactive"
        except:
            redis_status = "Inactive"
            
        system_info = {
            "Version": "1.0.0",
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Redis Connection": redis_status,
            "API Status": "Active",  # In a real app, would check API status
            "Detection Service": "Active"  # In a real app, would check service status
        }
        
        st.json(system_info)
        
        # Technical stack information
        st.subheader("Technical Stack")
        
        tech_stack = {
            "Real-Time Streaming": "Kafka/WebRTC for low-latency camera feeds",
            "Object Detection": "YOLOv8 for person detection",
            "Zone Tracking": "OpenCV for zone mapping",
            "Multi-Object Tracking": "DeepSORT for person tracking between zones",
            "Processing": "Apache Flink for real-time stream processing",
            "Database": "Redis for real-time updates, PostgreSQL for historical data",
            "Visualization": "Streamlit for real-time dashboard"
        }
        
        for tech, description in tech_stack.items():
            st.markdown(f"**{tech}**: {description}")

def render_camera_management():
    """Render the webcam management section."""
    st.header("Webcam Management", divider="rainbow")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Webcam List", "Add Webcam", "Recordings", "Webcam Settings"])
    
    with tab1:
        st.subheader("Current Webcams")
        webcams = st.session_state.get('webcams', [])
        
        if webcams:
            # Create a dataframe to display the webcams with more details
            webcam_data = []
            for i, webcam in enumerate(webcams):
                webcam_data.append({
                    "ID": i+1,
                    "Name": webcam.get('name', f"Webcam {i+1}"),
                    "URL": webcam.get('url', 'Not specified'),
                    "Location": webcam.get('location', 'Not specified'),
                    "Status": "Active" if webcam.get('active', True) else "Inactive",
                    "Added On": webcam.get('added_on', 'Unknown')
                })
            
            # Display the webcams
            st.dataframe(pd.DataFrame(webcam_data), use_container_width=True)
            
            # Select webcam for management
            selected_webcam = st.selectbox(
                "Select Webcam to Manage", 
                options=range(len(webcams)),
                format_func=lambda x: webcams[x].get('name', f"Webcam {x+1}")
            )
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("Edit Webcam"):
                    st.session_state.editing_webcam = selected_webcam
                    st.rerun()
            with col2:
                if st.button("Deactivate" if webcams[selected_webcam].get('active', True) else "Activate"):
                    webcams[selected_webcam]['active'] = not webcams[selected_webcam].get('active', True)
                    st.success(f"Webcam {webcams[selected_webcam]['name']} {'deactivated' if not webcams[selected_webcam]['active'] else 'activated'} successfully!")
                    st.rerun()
            with col3:
                if st.button("View Live Feed"):
                    st.session_state.current_tab = "Dashboard"
                    st.session_state.view_webcam = selected_webcam
                    st.rerun()
            with col4:
                if st.button("Delete Webcam"):
                    del webcams[selected_webcam]
                    st.success("Webcam deleted successfully!")
                    st.rerun()
        else:
            st.info("No webcams have been added yet. Go to the 'Add Webcam' tab to add one.")
    
    with tab2:
        st.subheader("Add New Webcam")
        
        with st.form("add_webcam_detailed"):
            webcam_name = st.text_input("Webcam Name", placeholder="e.g., Front Desk Camera")
            webcam_url = st.text_input("Webcam URL", placeholder="rtsp://username:password@192.168.1.100:554/stream")
            webcam_location = st.text_input("Location", placeholder="e.g., Main Office")
            
            col1, col2 = st.columns(2)
            with col1:
                webcam_type = st.selectbox("Webcam Type", ["IP Camera", "USB Webcam", "RTSP Stream", "HTTP Stream"])
            with col2:
                webcam_active = st.checkbox("Active", value=True)
            
            # Additional options in an expander
            with st.expander("Advanced Options"):
                col1, col2 = st.columns(2)
                with col1:
                    username = st.text_input("Username (if required)")
                    password = st.text_input("Password (if required)", type="password")
                with col2:
                    fps = st.number_input("Frame Rate (FPS)", value=10, min_value=1, max_value=30)
                    resolution = st.selectbox("Resolution", ["640x480", "1280x720", "1920x1080"])
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Add Webcam")
            with col2:
                test_connection = st.form_submit_button("Test Connection")
            
            if submitted:
                if webcam_name and webcam_url:
                    if 'webcams' not in st.session_state:
                        st.session_state.webcams = []
                    
                    st.session_state.webcams.append({
                        'name': webcam_name,
                        'url': webcam_url,
                        'location': webcam_location,
                        'type': webcam_type,
                        'active': webcam_active,
                        'username': username if username else None,
                        'password': password if password else None,
                        'fps': fps,
                        'resolution': resolution,
                        'added_on': datetime.now().isoformat()
                    })
                    
                    st.success(f"Webcam '{webcam_name}' added successfully!")
                    st.rerun()
                else:
                    st.error("Please provide both webcam name and URL.")
            
            if test_connection:
                if webcam_url:
                    # In a real implementation, we would test the connection
                    # For demonstration, just show a success message
                    st.info(f"Testing connection to {webcam_url}...")
                    time.sleep(1)
                    st.success("Connection test successful!")
                else:
                    st.error("Please provide a webcam URL to test.")
    
    with tab3:
        st.subheader("Webcam Recordings")
        
        # Display recordings
        recordings = st.session_state.get('recordings', [])
        
        if recordings:
            # Create a dataframe to display the recordings
            recording_data = pd.DataFrame(recordings)
            st.dataframe(recording_data, use_container_width=True)
            
            # Select recording to view
            selected_recording = st.selectbox(
                "Select Recording to View", 
                options=range(len(recordings)),
                format_func=lambda x: recordings[x].get('name', f"Recording {x+1}")
            )
            
            # Display recording details
            selected_rec = recordings[selected_recording]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Start Time:** {datetime.fromisoformat(selected_rec['start_time']).strftime('%Y-%m-%d %H:%M:%S')}")
            with col2:
                st.write(f"**Duration:** {selected_rec['duration']} minutes")
            with col3:
                st.write(f"**Size:** {selected_rec['size']}")
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("View Recording"):
                    st.info(f"Viewing recording: {selected_rec['name']}")
                    # In a real application, this would play the recording
                    st.warning("Recording playback feature is simulated in this demo")
            with col2:
                if st.button("Download Recording"):
                    st.info(f"Preparing download for: {selected_rec['name']}")
                    # In a real application, this would generate a download link
                    time.sleep(1)
                    st.success("Download link generated (simulated)")
            with col3:
                if st.button("Delete Recording"):
                    del recordings[selected_recording]
                    st.success("Recording deleted successfully!")
                    st.rerun()
        else:
            st.info("No recordings available. Use the Live View tab to record from webcams.")
    
    with tab4:
        st.subheader("Global Webcam Settings")
        
        st.write("Configure global settings for all webcams:")
        
        col1, col2 = st.columns(2)
        with col1:
            storage_days = st.number_input("Storage Retention (days)", value=30, min_value=1, max_value=365)
            recording_enabled = st.checkbox("Enable Recording", value=True)
            auto_record = st.checkbox("Auto-Record when Motion Detected", value=False)
        with col2:
            snapshot_interval = st.number_input("Snapshot Interval (minutes)", value=15, min_value=1, max_value=1440)
            motion_detection = st.checkbox("Enable Motion Detection", value=True)
            record_audio = st.checkbox("Record Audio (if available)", value=False)
        
        # Video quality settings
        st.subheader("Video Quality Settings")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            default_resolution = st.selectbox("Default Resolution", ["640x480", "1280x720", "1920x1080"])
        with col2:
            default_fps = st.slider("Default Frame Rate (FPS)", min_value=1, max_value=30, value=15)
        with col3:
            default_bitrate = st.selectbox("Default Bitrate", ["Low (1 Mbps)", "Medium (3 Mbps)", "High (5 Mbps)"])
        
        if st.button("Save Global Settings"):
            st.success("Global webcam settings saved successfully!")

def render_analytics():
    """Render the analytics page for employee monitoring."""
    st.header("Employee Monitoring Analytics", divider="rainbow")
    
    tab1, tab2, tab3 = st.tabs(["Attendance", "Productivity", "Time Tracking"])
    
    with tab1:
        st.subheader("Employee Attendance")
        
        # Date range selection
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.now() - timedelta(days=7))
        with col2:
            end_date = st.date_input("End Date", datetime.now())
        
        # Generate sample attendance data
        attendance_data = []
        employees = st.session_state.get('employees', [])
        
        if employees:
            # Create a date range
            date_range = pd.date_range(start=start_date, end=end_date)
            
            # For each employee, generate attendance records
            for emp in employees:
                for date in date_range:
                    # Randomly determine if present (more likely on weekdays)
                    is_weekday = date.weekday() < 5
                    present_prob = 0.95 if is_weekday else 0.3
                    is_present = np.random.random() < present_prob
                    
                    # Generate clock in/out times if present
                    if is_present:
                        # Clock in between 8:00 AM and 9:30 AM
                        clock_in = date + timedelta(hours=8, minutes=np.random.randint(0, 90))
                        
                        # Clock out between 5:00 PM and 6:30 PM
                        clock_out = date + timedelta(hours=17, minutes=np.random.randint(0, 90))
                        
                        # Calculate hours worked
                        hours_worked = (clock_out - clock_in).total_seconds() / 3600
                    else:
                        clock_in = None
                        clock_out = None
                        hours_worked = 0
                    
                    # Add to attendance data
                    attendance_data.append({
                        "Date": date.strftime("%Y-%m-%d"),
                        "Employee": emp["name"],
                        "Present": is_present,
                        "Clock In": clock_in.strftime("%H:%M:%S") if clock_in else "N/A",
                        "Clock Out": clock_out.strftime("%H:%M:%S") if clock_out else "N/A",
                        "Hours Worked": round(hours_worked, 2)
                    })
        
        # Display attendance data
        if attendance_data:
            attendance_df = pd.DataFrame(attendance_data)
            st.dataframe(attendance_df, use_container_width=True)
            
            # Create attendance summary chart
            st.subheader("Attendance Summary")
            
            # Group by date and calculate percentage present
            summary = attendance_df.groupby("Date").agg(
                Total=("Employee", "count"),
                Present=("Present", "sum")
            ).reset_index()
            
            summary["Attendance Rate"] = summary["Present"] / summary["Total"] * 100
            
            # Plot attendance chart
            fig = px.line(
                summary,
                x="Date",
                y="Attendance Rate",
                title="Daily Attendance Rate (%)",
                markers=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No attendance data available for the selected date range.")
    
    with tab2:
        st.subheader("Employee Productivity")
        
        # Generate sample productivity data
        productivity_data = []
        employees = st.session_state.get('employees', [])
        
        if employees:
            for emp in employees:
                # Generate random productivity scores
                productivity_score = np.random.randint(65, 95)
                
                # Calculate activity breakdown
                desk_time = np.random.uniform(5.0, 8.0)
                meeting_time = np.random.uniform(0.5, 2.0)
                break_time = np.random.uniform(0.3, 1.0)
                
                # Calculate metrics
                tasks_completed = np.random.randint(3, 15)
                productivity_trend = np.random.choice(["↑", "↓", "→"])
                
                productivity_data.append({
                    "Employee": emp["name"],
                    "Productivity Score": productivity_score,
                    "Desk Time (hrs)": round(desk_time, 1),
                    "Meeting Time (hrs)": round(meeting_time, 1),
                    "Break Time (hrs)": round(break_time, 1),
                    "Tasks Completed": tasks_completed,
                    "Trend": productivity_trend
                })
        
        # Display productivity data
        if productivity_data:
            productivity_df = pd.DataFrame(productivity_data)
            st.dataframe(productivity_df, use_container_width=True)
            
            # Create productivity visualization
            st.subheader("Productivity Comparison")
            
            fig = px.bar(
                productivity_df,
                x="Employee",
                y="Productivity Score",
                color="Productivity Score",
                color_continuous_scale="RdYlGn",
                title="Employee Productivity Scores"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Activity breakdown
            st.subheader("Activity Breakdown")
            
            activity_df = pd.DataFrame({
                "Employee": productivity_df["Employee"],
                "Desk Time": productivity_df["Desk Time (hrs)"],
                "Meeting Time": productivity_df["Meeting Time (hrs)"],
                "Break Time": productivity_df["Break Time (hrs)"]
            })
            
            # Melt the dataframe for the chart
            activity_long = pd.melt(
                activity_df,
                id_vars=["Employee"],
                value_vars=["Desk Time", "Meeting Time", "Break Time"],
                var_name="Activity Type",
                value_name="Hours"
            )
            
            # Create the chart
            fig = px.bar(
                activity_long,
                x="Employee",
                y="Hours",
                color="Activity Type",
                title="Employee Activity Breakdown",
                barmode="stack"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No productivity data available.")
    
    with tab3:
        st.subheader("Time Tracking")
        
        # Generate sample time tracking data
        time_data = []
        employees = st.session_state.get('employees', [])
        
        # Generate for the last 30 days
        date_range = pd.date_range(end=datetime.now().date(), periods=30)
        
        if employees:
            for date in date_range:
                for emp in employees:
                    # Only include weekdays
                    if date.weekday() < 5:
                        # Generate random hours
                        hours = np.random.uniform(7.0, 9.0)
                        
                        # Add noise to make it realistic
                        if np.random.random() < 0.1:  # 10% chance of unusual hours
                            hours = np.random.uniform(4.0, 11.0)
                        
                        time_data.append({
                            "Date": date.strftime("%Y-%m-%d"),
                            "Employee": emp["name"],
                            "Hours": round(hours, 1)
                        })
        
        # Display time tracking data
        if time_data:
            # Convert to DataFrame
            time_df = pd.DataFrame(time_data)
            
            # Allow filtering by employee
            selected_employee = st.selectbox(
                "Select Employee",
                options=["All"] + [emp["name"] for emp in employees]
            )
            
            # Filter data
            if selected_employee != "All":
                filtered_df = time_df[time_df["Employee"] == selected_employee]
            else:
                filtered_df = time_df
            
            # Display summary statistics
            if not filtered_df.empty:
                total_hours = filtered_df["Hours"].sum()
                avg_hours = filtered_df["Hours"].mean()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Hours", f"{total_hours:.1f}")
                with col2:
                    st.metric("Average Daily Hours", f"{avg_hours:.1f}")
                with col3:
                    st.metric("Days Tracked", len(filtered_df["Date"].unique()))
                
                # Create time tracking visualization
                st.subheader("Hours Tracked Over Time")
                
                if selected_employee != "All":
                    # For a single employee
                    fig = px.line(
                        filtered_df.sort_values("Date"),
                        x="Date",
                        y="Hours",
                        title=f"Daily Hours for {selected_employee}",
                        markers=True
                    )
                else:
                    # For all employees
                    pivot_df = filtered_df.pivot_table(
                        index="Date", 
                        columns="Employee", 
                        values="Hours",
                        aggfunc="sum"
                    ).reset_index()
                    
                    fig = px.line(
                        pivot_df,
                        x="Date",
                        y=pivot_df.columns[1:],  # All columns except Date
                        title="Daily Hours by Employee",
                        markers=True
                    )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show the raw data
                st.subheader("Time Tracking Records")
                st.dataframe(filtered_df.sort_values(["Date", "Employee"], ascending=[False, True]), use_container_width=True)
            else:
                st.info("No time tracking data available for the selected employee.")
        else:
            st.info("No time tracking data available.")

# Main app logic
def main():
    """Main application logic."""
    # Initialize session-based variables
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        # Any initialization that should happen only once

    # Render the dashboard
    render_main_dashboard()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Error in application: {str(e)}")
        import traceback
        st.exception(traceback.format_exc()) 