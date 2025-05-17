# Real-Time Space Monitoring System

A comprehensive system for monitoring and analyzing space utilization in office and educational environments using computer vision and real-time analytics.

## Features

- Real-time person detection and tracking
- Zone-based monitoring (desks, meeting rooms, break areas)
- Productive time calculation
- Real-time heatmaps and analytics
- Anomaly detection for unauthorized access and idle time
- Historical analytics dashboard

## Project Structure

```
├── src/
│   ├── detection/         # Object detection and tracking
│   ├── zones/            # Zone management and mapping
│   ├── analytics/        # Time calculation and analytics
│   ├── database/         # Database models and operations
│   ├── api/              # REST API endpoints
│   └── dashboard/        # Streamlit dashboard
├── config/               # Configuration files
├── tests/               # Unit tests
└── docs/                # Documentation
```

## Setup Instructions

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the system:
```bash
# Start the detection service
python src/detection/main.py

# Start the dashboard
streamlit run src/dashboard/app.py
```

## Configuration

The system requires configuration for:
- Camera feeds
- Zone definitions
- Database connections
- Alert thresholds

See `config/config.yaml` for detailed configuration options.

## License

MIT License 