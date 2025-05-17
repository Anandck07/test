import React, { useEffect, useState } from "react";
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Grid,
  Card,
  CardContent,
  CardMedia,
  CircularProgress,
  Button,
} from "@mui/material";
import axios from "axios";

const API_BASE = "http://localhost:8000"; // Change if needed

function CameraCard({ camera }) {
  const [frame, setFrame] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios
      .get(`${API_BASE}/frame/${camera.id}`)
      .then((res) => {
        if (res.data.status === "success") {
          setFrame(res.data.frame);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [camera.id]);

  return (
    <Card sx={{ maxWidth: 345, m: 2 }}>
      {loading ? (
        <CircularProgress sx={{ m: 2 }} />
      ) : frame ? (
        <CardMedia
          component="img"
          height="200"
          image={`data:image/jpeg;base64,${frame}`}
          alt={camera.name}
        />
      ) : (
        <Typography sx={{ m: 2 }}>No frame available</Typography>
      )}
      <CardContent>
        <Typography variant="h6">{camera.name}</Typography>
        <Typography variant="body2" color="text.secondary">
          Source: {camera.source}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Zone: {camera.zone_type}
        </Typography>
      </CardContent>
    </Card>
  );
}

function App() {
  const [cameras, setCameras] = useState([]);

  useEffect(() => {
    axios.get(`${API_BASE}/cameras`).then((res) => setCameras(res.data.cameras));
  }, []);

  return (
    <div>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h5" sx={{ flexGrow: 1 }}>
            Space Monitoring Dashboard
          </Typography>
        </Toolbar>
      </AppBar>
      <Container sx={{ mt: 4 }}>
        <Typography variant="h4" gutterBottom>
          Cameras
        </Typography>
        <Grid container spacing={2}>
          {cameras.map((cam) => (
            <Grid item xs={12} sm={6} md={4} key={cam.id}>
              <CameraCard camera={cam} />
            </Grid>
          ))}
        </Grid>
      </Container>
    </div>
  );
}

export default App;