from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import yaml
from typing import Dict, List
from datetime import datetime, timedelta
import base64
import cv2
import numpy as np
import os
import time

# Load configuration
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

app = FastAPI(
    title="Space Monitoring API",
    description="API for accessing space monitoring data and analytics",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Space Monitoring API",
        "version": "1.0.0",
        "endpoints": [
            "/metrics",
            "/zones",
            "/anomalies",
            "/heatmap",
            "/cameras"
        ]
    }

@app.get("/cameras")
async def get_cameras():
    """Get available cameras."""
    return {"cameras": config['cameras']}

@app.post("/cameras/add")
async def add_camera(
    camera_name: str = Body(...),
    camera_url: str = Body(...),
    zone_type: str = Body(...),
    simulation_mode: bool = Body(False)
):
    """Add a new camera to the configuration."""
    try:
        # Skip camera validation if in simulation mode
        if not simulation_mode:
            # Validate camera URL by trying to open it
            cap = cv2.VideoCapture(camera_url)
            
            # Check if camera opened successfully with timeout
            success = False
            start_time = time.time()
            timeout = 5  # 5 seconds timeout
            
            while time.time() - start_time < timeout:
                if cap.isOpened():
                    success = True
                    break
                time.sleep(0.1)
            
            if not success:
                raise HTTPException(status_code=400, detail="Could not connect to camera")
            
            # Try to read a frame to further validate the connection
            ret, frame = cap.read()
            if not ret:
                cap.release()
                raise HTTPException(status_code=400, detail="Could not read frame from camera")
            
            cap.release()
        else:
            # In simulation mode, we don't validate the camera URL
            print(f"Adding camera in simulation mode: {camera_name}, URL: {camera_url}")
        
        # Create new camera config
        new_camera = {
            "id": f"cam{len(config['cameras']) + 1}",
            "name": camera_name,
            "source": camera_url,
            "resolution": [1280, 720],
            "fps": 30,
            "zone_type": zone_type,
            "simulation_mode": simulation_mode
        }
        
        # Add to config
        config['cameras'].append(new_camera)
        
        # Save to file
        with open("config/config.yaml", 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        
        return {"status": "success", "camera": new_camera}
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding camera: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """Get current monitoring metrics."""
    try:
        data = redis_client.get('latest_metrics')
        if data:
            return json.loads(data)
        raise HTTPException(status_code=404, detail="No metrics available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/zones")
async def get_zones():
    """Get zone information and current occupancy."""
    try:
        data = redis_client.get('latest_metrics')
        if data:
            metrics = json.loads(data)
            return {
                "zones": config['zones'],
                "occupancy": metrics.get('zone_occupancy', {}),
                "utilization": metrics.get('zone_utilization', {})
            }
        raise HTTPException(status_code=404, detail="No zone data available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anomalies")
async def get_anomalies(limit: int = 100):
    """Get recent anomalies."""
    try:
        data = redis_client.get('latest_metrics')
        if data:
            metrics = json.loads(data)
            anomalies = metrics.get('anomalies', [])[-limit:]
            return {"anomalies": anomalies}
        raise HTTPException(status_code=404, detail="No anomaly data available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/heatmap")
async def get_heatmap():
    """Get heatmap data for zone utilization."""
    try:
        data = redis_client.get('latest_metrics')
        if data:
            metrics = json.loads(data)
            heatmap_data = {
                zone: data['current']
                for zone, data in metrics.get('zone_utilization', {}).items()
            }
            return {"heatmap": heatmap_data}
        raise HTTPException(status_code=404, detail="No heatmap data available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/frame/{camera_id}")
async def get_latest_frame(camera_id: str):
    """Get the latest frame from a specific camera."""
    try:
        # Try to get camera-specific frame
        data = redis_client.get(f'latest_frame_{camera_id}')
        
        # Fallback to generic frame
        if not data:
            data = redis_client.get('latest_frame')
        
        if data:
            frame_data = json.loads(data)
            return {
                "status": "success",
                "timestamp": frame_data['timestamp'],
                "frame": frame_data['frame']  # Base64 encoded
            }
        return {"status": "no data"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/productivity")
async def get_productivity():
    """Get productivity metrics."""
    try:
        data = redis_client.get('latest_metrics')
        if data:
            metrics = json.loads(data)
            return {
                "productive_hours": metrics.get('productive_hours', {}),
                "meeting_hours": metrics.get('meeting_hours', {}),
                "break_hours": metrics.get('break_hours', {})
            }
        raise HTTPException(status_code=404, detail="No productivity data available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config['api']['host'], port=config['api']['port']) 