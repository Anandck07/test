import time
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
import numpy as np
from collections import defaultdict

class AnalyticsEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.analytics_config = config['analytics']
        
        # Initialize tracking data structures
        self.zone_history = defaultdict(list)  # zone -> [(person_id, entry_time, exit_time)]
        self.current_occupancy = defaultdict(set)  # zone -> set(person_ids)
        self.idle_tracking = defaultdict(float)  # person_id -> last_movement_time
        
        # Initialize metrics
        self.metrics = {
            'productive_hours': defaultdict(float),
            'meeting_hours': defaultdict(float),
            'break_hours': defaultdict(float),
            'zone_utilization': defaultdict(lambda: defaultdict(int)),
            'anomalies': []
        }
    
    def update(self, tracking_info: Dict):
        """Update analytics with new tracking information."""
        current_time = time.time()
        
        # Process tracked objects
        for person_id, data in tracking_info['tracked_objects'].items():
            current_zone = data['current_zone']
            last_zone = self._get_last_zone(person_id)
            
            # Handle zone changes
            if current_zone != last_zone:
                self._handle_zone_change(person_id, last_zone, current_zone, current_time)
            
            # Update idle tracking
            if current_zone:
                self.idle_tracking[person_id] = current_time
            
            # Check for anomalies
            self._check_anomalies(person_id, current_zone, current_time)
        
        # Update zone utilization metrics
        self._update_zone_utilization(tracking_info['zone_occupancy'])
    
    def _get_last_zone(self, person_id: int) -> str:
        """Get the last zone a person was in."""
        for zone, history in self.zone_history.items():
            for entry in reversed(history):
                if entry[0] == person_id and entry[2] is None:
                    return zone
        return None
    
    def _handle_zone_change(self, person_id: int, old_zone: str, new_zone: str, current_time: float):
        """Handle zone changes and update metrics."""
        # Close previous zone entry if exists
        if old_zone:
            for entry in reversed(self.zone_history[old_zone]):
                if entry[0] == person_id and entry[2] is None:
                    entry[2] = current_time
                    duration = entry[2] - entry[1]
                    self._update_metrics(old_zone, duration)
        
        # Start new zone entry
        if new_zone:
            self.zone_history[new_zone].append([person_id, current_time, None])
            self.current_occupancy[new_zone].add(person_id)
    
    def _update_metrics(self, zone: str, duration: float):
        """Update productivity metrics based on zone type and duration."""
        zone_type = self._get_zone_type(zone)
        if zone_type == 'productive':
            self.metrics['productive_hours'][zone] += duration / 3600  # Convert to hours
        elif zone_type == 'collaborative':
            self.metrics['meeting_hours'][zone] += duration / 3600
        elif zone_type == 'break':
            self.metrics['break_hours'][zone] += duration / 3600
    
    def _get_zone_type(self, zone: str) -> str:
        """Get the type of a zone from configuration."""
        for zone_type, zones in self.config['zones'].items():
            for z in zones:
                if z['name'] == zone:
                    return z['type']
        return None
    
    def _check_anomalies(self, person_id: int, current_zone: str, current_time: float):
        """Check for anomalies in tracking data."""
        # Check for idle time
        if current_zone and current_zone in self._get_productive_zones():
            idle_time = current_time - self.idle_tracking[person_id]
            if idle_time > self.analytics_config['idle_threshold_seconds']:
                self.metrics['anomalies'].append({
                    'type': 'idle_time',
                    'person_id': person_id,
                    'zone': current_zone,
                    'duration': idle_time,
                    'timestamp': datetime.fromtimestamp(current_time).isoformat()
                })
        
        # Check for unauthorized access
        if current_zone in self._get_restricted_zones():
            self.metrics['anomalies'].append({
                'type': 'unauthorized_access',
                'person_id': person_id,
                'zone': current_zone,
                'timestamp': datetime.fromtimestamp(current_time).isoformat()
            })
    
    def _get_productive_zones(self) -> List[str]:
        """Get list of productive zones."""
        return [z['name'] for z in self.config['zones']['desks']]
    
    def _get_restricted_zones(self) -> List[str]:
        """Get list of restricted zones."""
        return [z['name'] for z in self.config['zones']['meeting_rooms'] 
                if z.get('restricted', False)]
    
    def _update_zone_utilization(self, zone_occupancy: Dict):
        """Update zone utilization metrics."""
        for zone, occupants in zone_occupancy.items():
            self.metrics['zone_utilization'][zone]['current'] = len(occupants)
            self.metrics['zone_utilization'][zone]['total'] += 1
    
    def get_metrics(self) -> Dict:
        """Get current analytics metrics."""
        return {
            'productive_hours': dict(self.metrics['productive_hours']),
            'meeting_hours': dict(self.metrics['meeting_hours']),
            'break_hours': dict(self.metrics['break_hours']),
            'zone_utilization': {
                zone: {
                    'current': data['current'],
                    'average': data['current'] / data['total'] if data['total'] > 0 else 0
                }
                for zone, data in self.metrics['zone_utilization'].items()
            },
            'anomalies': self.metrics['anomalies'][-100:]  # Last 100 anomalies
        }
    
    def get_heatmap_data(self) -> Dict:
        """Get data for heatmap visualization."""
        heatmap_data = defaultdict(int)
        for zone, history in self.zone_history.items():
            for entry in history:
                if entry[2] is None:  # Current occupancy
                    heatmap_data[zone] += 1
                else:  # Historical data
                    duration = entry[2] - entry[1]
                    heatmap_data[zone] += duration / 3600  # Convert to hours
        
        return dict(heatmap_data) 