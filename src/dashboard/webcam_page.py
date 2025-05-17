import streamlit as st
import time
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import sys
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import calendar

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webcam.webcam_handler import WebcamHandler, create_demo_handler

def render_webcam_page():
    """Render webcam live view and recording page."""
    st.header("Live Webcam Monitoring", divider="rainbow")
    
    # Initialize session state for webcam handling
    if 'webcam_handler' not in st.session_state:
        # For demo purposes, create a simulated handler
        st.session_state.webcam_handler = create_demo_handler()
        st.session_state.webcam_active = False
        st.session_state.recording_active = False
        st.session_state.monitoring_active = False
        st.session_state.recordings = []
        st.session_state.webcam_placeholder = None
        st.session_state.frame_update_time = datetime.now()
    
    # Create tabs for different webcam functions
    tab1, tab2, tab3, tab4 = st.tabs(["Live View", "Recording", "Employee Monitoring", "Productivity Analytics"])
    
    with tab1:
        st.subheader("Live Webcam Feed")
        
        # Webcam selection
        webcams = st.session_state.get('webcams', [])
        if webcams:
            selected_webcam_index = st.selectbox(
                "Select Webcam", 
                options=range(len(webcams)),
                format_func=lambda x: webcams[x].get('name', f"Webcam {x+1}")
            )
            
            # Update webcam URL if selected
            if st.button("Connect to Selected Webcam"):
                webcam_url = webcams[selected_webcam_index].get('url')
                st.session_state.webcam_handler = WebcamHandler(webcam_url=webcam_url)
                st.success(f"Connected to webcam: {webcams[selected_webcam_index].get('name')}")
                st.session_state.webcam_active = True
                st.rerun()
        else:
            st.info("No webcams configured. Using demo webcam.")
        
        # Stream control
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start Stream" if not st.session_state.webcam_active else "Refresh Stream"):
                st.session_state.webcam_active = True
                # Ensure connection
                if not st.session_state.webcam_handler.connect():
                    st.warning("Failed to connect to webcam, using demo mode")
                st.rerun()
        with col2:
            if st.button("Stop Stream" if st.session_state.webcam_active else "Disconnect"):
                st.session_state.webcam_active = False
                st.session_state.webcam_handler.disconnect()
                st.rerun()
        
        # Create a placeholder for the stream
        stream_placeholder = st.empty()
        st.session_state.webcam_placeholder = stream_placeholder
        
        # Display the webcam stream
        if st.session_state.webcam_active:
            # Auto-refresh option
            auto_refresh = st.checkbox("Auto-refresh feed", value=True)
            refresh_rate = st.slider("Refresh rate (seconds)", min_value=1, max_value=10, value=2)
            
            try:
                # Get current image
                image = st.session_state.webcam_handler.get_pil_image()
                if image:
                    # Display the image
                    stream_placeholder.image(image, caption="Live Webcam Feed", use_container_width=True)
                    st.session_state.frame_update_time = datetime.now()
                else:
                    stream_placeholder.error("Failed to get webcam frame, check connection")
            except Exception as e:
                stream_placeholder.error(f"Error displaying webcam feed: {str(e)}")
                
            # Force refresh of webcam feed
            if auto_refresh:
                time.sleep(0.5)  # Brief pause to ensure UI renders
                st.rerun()
        else:
            stream_placeholder.info("Webcam stream is not active. Click 'Start Stream' to begin.")
    
    with tab2:
        st.subheader("Webcam Recording")
        
        # Recording controls
        col1, col2, col3 = st.columns(3)
        with col1:
            record_button = st.button(
                "Start Recording" if not st.session_state.recording_active else "Stop Recording"
            )
        with col2:
            recording_duration = st.number_input(
                "Recording Duration (seconds)", 
                min_value=5, 
                max_value=600, 
                value=30,
                disabled=st.session_state.recording_active
            )
        with col3:
            recording_name = st.text_input(
                "Recording Name (optional)", 
                placeholder="Leave blank for auto-naming",
                disabled=st.session_state.recording_active
            )
        
        # Handle recording controls
        if record_button:
            if not st.session_state.recording_active:
                # Start recording
                filename = None
                if recording_name:
                    filename = f"{recording_name}.mp4"
                
                # Ensure webcam is active
                if not st.session_state.webcam_active:
                    st.session_state.webcam_active = True
                    if not st.session_state.webcam_handler.connect():
                        st.warning("Failed to connect to webcam, using demo mode")
                
                # Start the recording
                success = st.session_state.webcam_handler.start_recording(
                    duration=recording_duration,
                    filename=filename
                )
                
                if success:
                    st.session_state.recording_active = True
                    st.session_state.recording_start_time = datetime.now()
                    st.success("Recording started")
                else:
                    st.error("Failed to start recording")
            else:
                # Stop recording
                filepath = st.session_state.webcam_handler.stop_recording()
                st.session_state.recording_active = False
                
                if filepath:
                    # Add to recordings list
                    recording_duration_actual = (datetime.now() - st.session_state.recording_start_time).total_seconds()
                    
                    # Check if file exists before accessing it
                    file_size = "N/A"
                    if os.path.exists(filepath):
                        file_size = f"{os.path.getsize(filepath) / (1024 * 1024):.1f} MB"
                    
                    st.session_state.recordings.append({
                        'name': os.path.basename(filepath),
                        'path': filepath,
                        'timestamp': st.session_state.recording_start_time.isoformat(),
                        'duration': recording_duration_actual,
                        'size': file_size
                    })
                    
                    st.success(f"Recording saved: {filepath}")
                else:
                    st.warning("Recording stopped but no file was saved")
        
        # Show recording progress
        if st.session_state.recording_active:
            elapsed_time = (datetime.now() - st.session_state.recording_start_time).total_seconds()
            progress = min(elapsed_time / recording_duration, 1.0)
            
            st.progress(progress)
            st.info(f"Recording in progress: {int(elapsed_time)}s / {recording_duration}s")
        
        # Display recorded videos
        st.subheader("Recorded Videos")
        
        if st.session_state.recordings:
            # Create dataframe
            recordings_df = pd.DataFrame(st.session_state.recordings)
            st.dataframe(recordings_df, use_container_width=True)
            
            # Only show selection if recordings exist
            if len(st.session_state.recordings) > 0:
                # Select recording to view
                selected_recording = st.selectbox(
                    "Select Recording to View",
                    options=range(len(st.session_state.recordings)),
                    format_func=lambda x: st.session_state.recordings[x].get('name', f"Recording {x+1}")
                )
                
                # Action buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("View Recording"):
                        # In a real application, this would play the video
                        # For demo purposes, we'll just show a placeholder
                        st.info(f"Viewing recording: {st.session_state.recordings[selected_recording]['name']}")
                        st.warning("Video playback functionality is simulated in this demo")
                with col2:
                    if st.button("Delete Recording"):
                        # Delete the recording
                        filepath = st.session_state.recordings[selected_recording]['path']
                        if os.path.exists(filepath):
                            try:
                                os.remove(filepath)
                                st.success("File deleted successfully")
                            except Exception as e:
                                st.error(f"Error deleting file: {e}")
                        
                        # Remove from list
                        st.session_state.recordings.pop(selected_recording)
                        st.rerun()
        else:
            st.info("No recordings available")
    
    with tab3:
        st.subheader("Employee Monitoring")
        
        # Monitoring controls
        col1, col2 = st.columns(2)
        with col1:
            monitor_button = st.button(
                "Start Monitoring" if not st.session_state.monitoring_active else "Stop Monitoring"
            )
        with col2:
            monitor_sensitivity = st.slider(
                "Detection Sensitivity", 
                min_value=0.1, 
                max_value=1.0, 
                value=0.5,
                step=0.1,
                disabled=st.session_state.monitoring_active
            )
        
        # Handle monitoring controls
        if monitor_button:
            if not st.session_state.monitoring_active:
                # Ensure webcam is active
                if not st.session_state.webcam_active:
                    st.session_state.webcam_active = True
                    if not st.session_state.webcam_handler.connect():
                        st.warning("Failed to connect to webcam, using demo mode")
                
                # Start monitoring
                success = st.session_state.webcam_handler.start_employee_monitoring()
                if success:
                    st.session_state.monitoring_active = True
                    st.success("Employee monitoring started")
                else:
                    st.error("Failed to start monitoring")
            else:
                # Stop monitoring
                st.session_state.webcam_handler.stop_employee_monitoring()
                st.session_state.monitoring_active = False
                st.success("Employee monitoring stopped")
        
        # Display monitoring results
        if st.session_state.monitoring_active:
            # Refresh button
            if st.button("Refresh Data"):
                st.rerun()
            
            # Get employee data
            employee_data = st.session_state.webcam_handler.get_employee_data()
            
            if employee_data:
                # Process employee data
                employee_list = []
                for person_id, data in employee_data.items():
                    # Calculate time present
                    first_seen = data.get("first_seen", datetime.now())
                    last_seen = data.get("last_seen", datetime.now())
                    time_present = (last_seen - first_seen).total_seconds() / 60  # minutes
                    
                    # Get zone
                    zone = data.get("zone", "desk")
                    
                    # Create entry
                    employee_list.append({
                        "ID": person_id,
                        "First Seen": first_seen.strftime("%H:%M:%S"),
                        "Last Seen": last_seen.strftime("%H:%M:%S"),
                        "Time Present (min)": round(time_present, 1),
                        "Zone": zone.capitalize(),
                        "Activity Level": round(data.get("activity_level", 0) * 100, 1),
                        "Status": "Active" if data.get("activity_level", 0) > 0.3 else "Inactive"
                    })
                
                # Display as table
                if employee_list:
                    st.dataframe(pd.DataFrame(employee_list), use_container_width=True)
                    
                    # Create activity chart
                    st.subheader("Employee Activity Levels")
                    activity_df = pd.DataFrame(employee_list)
                    
                    fig = px.bar(
                        activity_df,
                        x="ID",
                        y="Activity Level",
                        color="Status",
                        color_discrete_map={"Active": "green", "Inactive": "red"},
                        title="Employee Activity Monitoring"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Add zone distribution pie chart
                    st.subheader("Employee Zone Distribution")
                    zone_counts = activity_df["Zone"].value_counts()
                    
                    fig_zone = px.pie(
                        values=zone_counts.values,
                        names=zone_counts.index,
                        title="Current Employee Zone Distribution"
                    )
                    
                    st.plotly_chart(fig_zone, use_container_width=True)
                    
                    # Employee count metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Employees", len(employee_list))
                    with col2:
                        active_count = len([e for e in employee_list if e["Status"] == "Active"])
                        st.metric("Active Employees", active_count)
                    with col3:
                        inactive_count = len([e for e in employee_list if e["Status"] == "Inactive"])
                        st.metric("Inactive Employees", inactive_count)
                else:
                    st.info("No employees detected")
            else:
                st.info("No monitoring data available yet")
        else:
            st.info("Employee monitoring is not active. Click 'Start Monitoring' to begin.")
            
    with tab4:
        st.header("Productivity & Space Analytics", divider="rainbow")
        
        # Start demo mode if not active
        if not st.session_state.webcam_active and not st.session_state.monitoring_active:
            # Show a button to start demo mode
            if st.button("Start Demo Analytics"):
                st.session_state.webcam_active = True
                st.session_state.monitoring_active = True
                st.session_state.webcam_handler.start_employee_monitoring()
                st.success("Demo analytics started")
                st.rerun()
        
        # Refresh button for analytics
        if st.button("Refresh Analytics Data"):
            st.rerun()
        
        # Get metrics data
        zone_data = st.session_state.webcam_handler.get_zone_data()
        productivity_metrics = st.session_state.webcam_handler.get_productivity_metrics()
        historical_data = st.session_state.webcam_handler.get_historical_data()
        
        # Create subtabs for different analytics
        subtab1, subtab2, subtab3, subtab4 = st.tabs(["Space Utilization", "Productivity Metrics", "Historical Trends", "Advanced Analytics"])
        
        with subtab1:
            st.subheader("Current Space Utilization")
            
            # Create zone utilization cards
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Desk areas utilization
                desk_capacity = zone_data.get("desk_areas", {}).get("capacity", 10)
                desk_current = zone_data.get("desk_areas", {}).get("current", 0)
                desk_utilization = (desk_current / desk_capacity) * 100 if desk_capacity > 0 else 0
                
                st.metric("Desk Areas", f"{desk_current}/{desk_capacity}", f"{desk_utilization:.1f}%")
                
                # Create progress bar
                st.progress(min(1.0, desk_current / desk_capacity))
            
            with col2:
                # Meeting rooms utilization
                meeting_capacity = zone_data.get("meeting_rooms", {}).get("capacity", 8)
                meeting_current = zone_data.get("meeting_rooms", {}).get("current", 0)
                meeting_utilization = (meeting_current / meeting_capacity) * 100 if meeting_capacity > 0 else 0
                
                st.metric("Meeting Rooms", f"{meeting_current}/{meeting_capacity}", f"{meeting_utilization:.1f}%")
                
                # Create progress bar
                st.progress(min(1.0, meeting_current / meeting_capacity))
            
            with col3:
                # Break areas utilization
                break_capacity = zone_data.get("break_areas", {}).get("capacity", 6)
                break_current = zone_data.get("break_areas", {}).get("current", 0)
                break_utilization = (break_current / break_capacity) * 100 if break_capacity > 0 else 0
                
                st.metric("Break Areas", f"{break_current}/{break_capacity}", f"{break_utilization:.1f}%")
                
                # Create progress bar
                st.progress(min(1.0, break_current / break_capacity))
            
            # Create overall utilization gauge
            overall_utilization = productivity_metrics.get("overall_utilization", 0) * 100
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=overall_utilization,
                title={"text": "Overall Space Utilization"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "green" if overall_utilization < 70 else "orange" if overall_utilization < 90 else "red"},
                    "steps": [
                        {"range": [0, 30], "color": "lightgray"},
                        {"range": [30, 70], "color": "lightgreen"},
                        {"range": [70, 90], "color": "lightsalmon"},
                        {"range": [90, 100], "color": "lightcoral"}
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": 90
                    }
                }
            ))
            
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with subtab2:
            st.subheader("Employee Productivity Metrics")
            
            # Get productivity data
            productive_hours = productivity_metrics.get("productive_hours", {})
            meeting_hours = productivity_metrics.get("meeting_hours", {})
            break_hours = productivity_metrics.get("break_hours", {})
            
            if productive_hours:
                # Process data for visualization
                productivity_data = []
                
                for person_id in productive_hours.keys():
                    productivity_data.append({
                        "Employee ID": person_id,
                        "Productive Hours": productive_hours.get(person_id, 0),
                        "Meeting Hours": meeting_hours.get(person_id, 0),
                        "Break Hours": break_hours.get(person_id, 0),
                        "Total Hours": productive_hours.get(person_id, 0) + meeting_hours.get(person_id, 0) + break_hours.get(person_id, 0)
                    })
                
                # Create dataframe
                productivity_df = pd.DataFrame(productivity_data)
                
                # Calculate productivity percentages
                productivity_df["Productive %"] = (productivity_df["Productive Hours"] / productivity_df["Total Hours"] * 100).round(1)
                productivity_df["Meeting %"] = (productivity_df["Meeting Hours"] / productivity_df["Total Hours"] * 100).round(1)
                productivity_df["Break %"] = (productivity_df["Break Hours"] / productivity_df["Total Hours"] * 100).round(1)
                
                # Display table
                st.dataframe(productivity_df, use_container_width=True)
                
                # Create stacked bar chart
                activity_data = []
                for item in productivity_data:
                    activity_data.append({
                        "Employee": item["Employee ID"],
                        "Activity": "Productive",
                        "Hours": item["Productive Hours"]
                    })
                    activity_data.append({
                        "Employee": item["Employee ID"],
                        "Activity": "Meeting",
                        "Hours": item["Meeting Hours"]
                    })
                    activity_data.append({
                        "Employee": item["Employee ID"],
                        "Activity": "Break",
                        "Hours": item["Break Hours"]
                    })
                
                activity_df = pd.DataFrame(activity_data)
                
                fig = px.bar(
                    activity_df,
                    x="Employee",
                    y="Hours",
                    color="Activity",
                    title="Employee Time Allocation",
                    color_discrete_map={
                        "Productive": "green",
                        "Meeting": "blue",
                        "Break": "orange"
                    }
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Create productivity pie chart
                total_productive = sum(productive_hours.values())
                total_meeting = sum(meeting_hours.values())
                total_break = sum(break_hours.values())
                
                fig_pie = px.pie(
                    values=[total_productive, total_meeting, total_break],
                    names=["Productive", "Meeting", "Break"],
                    title="Overall Time Allocation",
                    color_discrete_sequence=["green", "blue", "orange"]
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
                
                # Create efficiency ranking
                st.subheader("Employee Efficiency Ranking")
                
                # Calculate efficiency score (productive hours / total hours)
                ranking_df = productivity_df.copy()
                ranking_df["Efficiency Score"] = (ranking_df["Productive Hours"] / ranking_df["Total Hours"] * 100).round(1)
                ranking_df = ranking_df.sort_values("Efficiency Score", ascending=False)
                
                # Create bar chart
                fig_ranking = px.bar(
                    ranking_df,
                    x="Employee ID",
                    y="Efficiency Score",
                    color="Efficiency Score",
                    color_continuous_scale="RdYlGn",
                    title="Employee Efficiency Ranking"
                )
                
                st.plotly_chart(fig_ranking, use_container_width=True)
            else:
                st.info("No productivity data available yet. Start monitoring to collect data.")
        
        with subtab3:
            st.subheader("Historical Utilization Trends")
            
            if historical_data:
                # Convert to dataframe
                historical_df = pd.DataFrame(historical_data)
                
                # Convert timestamps to datetime
                historical_df['timestamp'] = pd.to_datetime(historical_df['timestamp'])
                
                # Add date components for filtering and aggregation
                historical_df['date'] = historical_df['timestamp'].dt.date
                historical_df['hour'] = historical_df['timestamp'].dt.hour
                historical_df['weekday'] = historical_df['timestamp'].dt.weekday
                historical_df['weekday_name'] = historical_df['timestamp'].dt.day_name()
                
                # Format for display
                historical_df['Time'] = historical_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                historical_df['Desk Utilization'] = historical_df['desk_occupancy_rate'] * 100
                historical_df['Meeting Room Utilization'] = historical_df['meeting_room_utilization'] * 100
                historical_df['Break Area Utilization'] = historical_df['break_area_utilization'] * 100
                historical_df['Overall Utilization'] = historical_df['overall_utilization'] * 100
                
                # Date range selector
                date_min = historical_df['date'].min()
                date_max = historical_df['date'].max()
                
                date_range = st.date_input(
                    "Select Date Range",
                    value=(date_min, date_max),
                    min_value=date_min,
                    max_value=date_max
                )
                
                # Filter by date range
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    filtered_df = historical_df[(historical_df['date'] >= start_date) & (historical_df['date'] <= end_date)]
                else:
                    filtered_df = historical_df
                
                # Create line chart for space utilization
                fig = px.line(
                    filtered_df,
                    x='timestamp',
                    y=['Desk Utilization', 'Meeting Room Utilization', 'Break Area Utilization', 'Overall Utilization'],
                    title="Space Utilization Over Time",
                    markers=True
                )
                
                fig.update_layout(
                    xaxis_title="Time",
                    yaxis_title="Utilization (%)",
                    yaxis_range=[0, 100],
                    legend_title="Space Type"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Create employee count chart
                fig2 = px.line(
                    filtered_df,
                    x='timestamp',
                    y=['employee_count', 'active_employees'],
                    title="Employee Count Over Time",
                    markers=True,
                    color_discrete_sequence=['blue', 'green']
                )
                
                fig2.update_layout(
                    xaxis_title="Time",
                    yaxis_title="Count",
                    legend_title="Employee Status"
                )
                
                st.plotly_chart(fig2, use_container_width=True)
                
                # Create productive hours chart if available
                if 'total_productive_hours' in filtered_df.columns:
                    # Create productivity hours chart
                    fig3 = px.line(
                        filtered_df,
                        x='timestamp',
                        y=['total_productive_hours', 'total_meeting_hours', 'total_break_hours'],
                        title="Total Hours by Activity Type",
                        markers=True,
                        color_discrete_sequence=['green', 'blue', 'orange']
                    )
                    
                    fig3.update_layout(
                        xaxis_title="Time",
                        yaxis_title="Total Hours",
                        legend_title="Activity Type"
                    )
                    
                    st.plotly_chart(fig3, use_container_width=True)
                
                # Show raw data in an expander
                with st.expander("View Raw Historical Data"):
                    st.dataframe(filtered_df[['Time', 'Desk Utilization', 'Meeting Room Utilization', 
                                              'Break Area Utilization', 'Overall Utilization', 
                                              'employee_count', 'active_employees']], 
                                use_container_width=True)
            else:
                st.info("No historical data available yet. Continue monitoring to collect data.")
                
        with subtab4:
            st.subheader("Advanced Space Utilization Analytics")
            
            if historical_data and len(historical_data) > 1:
                # Convert to dataframe
                historical_df = pd.DataFrame(historical_data)
                
                # Convert timestamps to datetime
                historical_df['timestamp'] = pd.to_datetime(historical_df['timestamp'])
                
                # Add date components for filtering and aggregation
                historical_df['date'] = historical_df['timestamp'].dt.date
                historical_df['hour'] = historical_df['timestamp'].dt.hour
                historical_df['weekday'] = historical_df['timestamp'].dt.weekday
                historical_df['weekday_name'] = historical_df['timestamp'].dt.day_name()
                
                # Format for display
                historical_df['Desk Utilization'] = historical_df['desk_occupancy_rate'] * 100
                historical_df['Meeting Room Utilization'] = historical_df['meeting_room_utilization'] * 100
                historical_df['Break Area Utilization'] = historical_df['break_area_utilization'] * 100
                
                # Create hourly aggregation
                hourly_df = historical_df.groupby('hour').agg({
                    'Desk Utilization': 'mean',
                    'Meeting Room Utilization': 'mean',
                    'Break Area Utilization': 'mean',
                    'Overall Utilization': 'mean',
                    'employee_count': 'mean'
                }).reset_index()
                
                # 1. Peak Usage Hours
                st.subheader("Peak Usage Hours")
                
                # Create hourly utilization heatmap
                fig_hourly = px.bar(
                    hourly_df,
                    x='hour',
                    y=['Desk Utilization', 'Meeting Room Utilization', 'Break Area Utilization'],
                    title="Average Space Utilization by Hour",
                    barmode='group'
                )
                
                fig_hourly.update_layout(
                    xaxis_title="Hour of Day",
                    yaxis_title="Average Utilization (%)",
                    xaxis=dict(
                        tickmode='array',
                        tickvals=list(range(24)),
                        ticktext=[f"{h}:00" for h in range(24)]
                    )
                )
                
                st.plotly_chart(fig_hourly, use_container_width=True)
                
                # 2. Weekday Patterns
                if len(historical_df['weekday'].unique()) > 1:
                    st.subheader("Weekday Utilization Patterns")
                    
                    # Create weekday aggregation
                    weekday_df = historical_df.groupby('weekday').agg({
                        'Desk Utilization': 'mean',
                        'Meeting Room Utilization': 'mean',
                        'Break Area Utilization': 'mean',
                        'Overall Utilization': 'mean',
                        'employee_count': 'mean'
                    }).reset_index()
                    
                    # Add weekday names
                    weekday_df['weekday_name'] = weekday_df['weekday'].apply(lambda x: calendar.day_name[x])
                    weekday_df = weekday_df.sort_values('weekday')
                    
                    # Create weekday utilization chart
                    fig_weekday = px.line(
                        weekday_df,
                        x='weekday_name',
                        y=['Desk Utilization', 'Meeting Room Utilization', 'Break Area Utilization', 'Overall Utilization'],
                        title="Average Space Utilization by Day of Week",
                        markers=True
                    )
                    
                    fig_weekday.update_layout(
                        xaxis_title="Day of Week",
                        yaxis_title="Average Utilization (%)"
                    )
                    
                    st.plotly_chart(fig_weekday, use_container_width=True)
                
                # 3. Utilization Heatmap
                st.subheader("Space Utilization Heatmap")
                
                # Create hourly-weekday pivot
                if len(historical_df['weekday'].unique()) > 1 and len(historical_df['hour'].unique()) > 1:
                    heatmap_data = historical_df.pivot_table(
                        index='weekday', 
                        columns='hour', 
                        values='Overall Utilization',
                        aggfunc='mean'
                    )
                    
                    # Create the heatmap
                    fig_heatmap = px.imshow(
                        heatmap_data,
                        labels=dict(x="Hour of Day", y="Day of Week", color="Utilization (%)"),
                        x=[f"{h}:00" for h in range(24) if h in heatmap_data.columns],
                        y=[calendar.day_name[day] for day in heatmap_data.index],
                        color_continuous_scale="RdYlGn_r",
                        title="Space Utilization Heatmap by Hour and Day"
                    )
                    
                    st.plotly_chart(fig_heatmap, use_container_width=True)
                
                # 4. Productivity Analysis
                if 'total_productive_hours' in historical_df.columns:
                    st.subheader("Productivity Analytics")
                    
                    # Create daily aggregation
                    daily_df = historical_df.groupby('date').agg({
                        'employee_count': 'mean',
                        'total_productive_hours': 'mean',
                        'total_meeting_hours': 'mean',
                        'total_break_hours': 'mean'
                    }).reset_index()
                    
                    # Create efficiency metrics
                    daily_df['Productivity per Employee'] = daily_df['total_productive_hours'] / daily_df['employee_count']
                    daily_df['Meeting Hours per Employee'] = daily_df['total_meeting_hours'] / daily_df['employee_count']
                    
                    # Create productivity per employee chart
                    fig_prod = px.line(
                        daily_df,
                        x='date',
                        y=['Productivity per Employee', 'Meeting Hours per Employee'],
                        title="Average Hours per Employee by Day",
                        markers=True
                    )
                    
                    fig_prod.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Hours per Employee"
                    )
                    
                    st.plotly_chart(fig_prod, use_container_width=True)
                    
                    # Productivity vs. Occupancy Correlation
                    st.subheader("Productivity vs. Space Occupancy Correlation")
                    
                    # Create correlation chart using a scatter plot
                    fig_corr = px.scatter(
                        historical_df,
                        x='Overall Utilization',
                        y='total_productive_hours',
                        trendline="ols",
                        title="Correlation: Space Utilization vs. Productive Hours"
                    )
                    
                    fig_corr.update_layout(
                        xaxis_title="Overall Space Utilization (%)",
                        yaxis_title="Total Productive Hours"
                    )
                    
                    st.plotly_chart(fig_corr, use_container_width=True)
            else:
                st.info("Not enough historical data for advanced analytics. Continue monitoring to collect more data.")

if __name__ == "__main__":
    # This allows the page to be run directly for testing
    render_webcam_page() 