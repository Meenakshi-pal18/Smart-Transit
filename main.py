from __future__ import annotations

import json
import math
import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import create_user, get_user_by_email, init_db, store_sync_event, verify_user
from model import ETAModelService, load_or_train_model

app = FastAPI(title="SmartTransit Resilient Tracker API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

eta_service: ETAModelService = load_or_train_model()
active_tokens: Dict[str, Dict[str, str]] = {}

ROUTES = {
    "a1": {
        "name": "Bus A1",
        "route_name": "North Gate Loop",
        "stops": [
            {"name": "Main Gate", "lat": 12.9716, "lng": 77.5946},
            {"name": "Hostel Block", "lat": 12.9740, "lng": 77.5983},
            {"name": "Engineering Block", "lat": 12.9775, "lng": 77.6014},
            {"name": "Sports Complex", "lat": 12.9801, "lng": 77.6052},
            {"name": "Library", "lat": 12.9827, "lng": 77.6084},
        ],
        "speed": 28,
        "delay": 2.4,
    },
    "b2": {
        "name": "Bus B2",
        "route_name": "City Side Connector",
        "stops": [
            {"name": "Admin Block", "lat": 12.9694, "lng": 77.5896},
            {"name": "Auditorium", "lat": 12.9710, "lng": 77.5927},
            {"name": "Library", "lat": 12.9739, "lng": 77.5962},
            {"name": "Medical Center", "lat": 12.9767, "lng": 77.6009},
            {"name": "North Gate", "lat": 12.9792, "lng": 77.6050},
        ],
        "speed": 24,
        "delay": 4.1,
    },
    "c3": {
        "name": "Bus C3",
        "route_name": "Hostel Rapid",
        "stops": [
            {"name": "South Gate", "lat": 12.9641, "lng": 77.5880},
            {"name": "Cafeteria", "lat": 12.9668, "lng": 77.5912},
            {"name": "Lab Complex", "lat": 12.9695, "lng": 77.5950},
            {"name": "Boys Hostel", "lat": 12.9724, "lng": 77.5986},
            {"name": "Girls Hostel", "lat": 12.9751, "lng": 77.6020},
        ],
        "speed": 20,
        "delay": 5.6,
    },
    "d4": {
        "name": "Bus D4",
        "route_name": "East Campus Arc",
        "stops": [
            {"name": "Innovation Hub", "lat": 12.9755, "lng": 77.6074},
            {"name": "Seminar Hall", "lat": 12.9781, "lng": 77.6095},
            {"name": "Library", "lat": 12.9800, "lng": 77.6121},
            {"name": "MBA Block", "lat": 12.9827, "lng": 77.6140},
            {"name": "Research Park", "lat": 12.9854, "lng": 77.6173},
        ],
        "speed": 26,
        "delay": 2.0,
    },
    "e5": {
        "name": "Bus E5",
        "route_name": "West Residence Shuttle",
        "stops": [
            {"name": "West Hostel", "lat": 12.9680, "lng": 77.5818},
            {"name": "Design Block", "lat": 12.9702, "lng": 77.5853},
            {"name": "Main Quadrangle", "lat": 12.9727, "lng": 77.5892},
            {"name": "Admin Block", "lat": 12.9751, "lng": 77.5927},
            {"name": "North Gate", "lat": 12.9775, "lng": 77.5968},
        ],
        "speed": 22,
        "delay": 3.4,
    },
    "f6": {
        "name": "Bus F6",
        "route_name": "Metro Feeder",
        "stops": [
            {"name": "Metro Station", "lat": 12.9601, "lng": 77.6021},
            {"name": "South Gate", "lat": 12.9633, "lng": 77.6015},
            {"name": "Law Block", "lat": 12.9675, "lng": 77.6009},
            {"name": "Central Plaza", "lat": 12.9712, "lng": 77.6001},
            {"name": "Library", "lat": 12.9754, "lng": 77.5988},
        ],
        "speed": 25,
        "delay": 4.8,
    },
    "g7": {
        "name": "Bus G7",
        "route_name": "Circular Green Route",
        "stops": [
            {"name": "Garden View", "lat": 12.9718, "lng": 77.6094},
            {"name": "Biotech Block", "lat": 12.9739, "lng": 77.6122},
            {"name": "Library", "lat": 12.9759, "lng": 77.6149},
            {"name": "Sports Complex", "lat": 12.9784, "lng": 77.6126},
            {"name": "North Gate", "lat": 12.9798, "lng": 77.6091},
        ],
        "speed": 27,
        "delay": 1.7,
    },
    "h8": {
        "name": "Bus H8",
        "route_name": "Exam Special Line",
        "stops": [
            {"name": "Exam Hall", "lat": 12.9659, "lng": 77.5943},
            {"name": "Civil Block", "lat": 12.9686, "lng": 77.5974},
            {"name": "Engineering Block", "lat": 12.9718, "lng": 77.6005},
            {"name": "Central Plaza", "lat": 12.9752, "lng": 77.6039},
            {"name": "Hostel Block", "lat": 12.9785, "lng": 77.6071},
        ],
        "speed": 21,
        "delay": 6.1,
    },
}


class AuthPayload(BaseModel):
    email: EmailStr
    password: str


class SignupPayload(AuthPayload):
    name: str


class ETAPayload(BaseModel):
    distance_km: float
    speed_kmph: float
    historical_delay: float


class SyncPayload(BaseModel):
    events: List[dict]


class Bus(BaseModel):
    id: str
    name: str
    route: str
    latitude: float
    longitude: float
    speed: int
    eta: float
    status: str


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def create_token(user: Dict[str, str]) -> str:
    token = uuid4().hex
    active_tokens[token] = user
    return token


def require_auth(authorization: Optional[str]) -> Dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "").strip()
    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")
    return active_tokens[token]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def interpolate_segment(first: dict, second: dict, ratio: float) -> dict:
    return {
        "lat": first["lat"] + (second["lat"] - first["lat"]) * ratio,
        "lng": first["lng"] + (second["lng"] - first["lng"]) * ratio,
    }


def simulate_network_delay(network_tier: str) -> None:
    if network_tier == "weak":
        time.sleep(random.uniform(0.8, 1.5))
    elif network_tier == "offline":
        raise HTTPException(status_code=503, detail="Network offline. Using local buffer.")
    else:
        time.sleep(random.uniform(0.08, 0.26))


def build_bus_state(bus_id: str, route: dict, network_tier: str) -> dict:
    stops = route["stops"]
    total_segments = len(stops) - 1
    base_cycle = (time.time() / (10 if network_tier == "good" else 18)) + (hash(bus_id) % 5)
    progress = base_cycle % total_segments
    segment_index = min(int(progress), total_segments - 1)
    ratio = progress - segment_index

    current = stops[segment_index]
    nxt = stops[segment_index + 1]
    interpolated = interpolate_segment(current, nxt, ratio)

    remaining_distance = haversine_km(interpolated["lat"], interpolated["lng"], nxt["lat"], nxt["lng"])
    eta_minutes = eta_service.predict_minutes(
        distance_km=remaining_distance + random.uniform(0.2, 1.4),
        speed_kmph=route["speed"] - (2 if network_tier == "weak" else 0),
        historical_delay=route["delay"],
    )

    preview = [
        interpolated,
        nxt,
        stops[min(segment_index + 2, len(stops) - 1)],
    ]

    state = {
        "id": bus_id,
        "name": route["name"],
        "route_name": route["route_name"],
        "latitude": round(interpolated["lat"], 6),
        "longitude": round(interpolated["lng"], 6),
        "current_location_label": f"Near {current['name']}",
        "next_stop": nxt["name"],
        "eta_minutes": eta_minutes,
        "speed_kmph": route["speed"],
        "historical_delay": route["delay"],
        "status": "Weak Signal" if network_tier == "weak" else "On Route",
        "network_hint": "Compressed payload" if network_tier == "weak" else "Full fidelity",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path_preview": preview,
    }

    if network_tier == "weak":
        return {
            key: value
            for key, value in state.items()
            if key in {
                "id",
                "name",
                "route_name",
                "latitude",
                "longitude",
                "current_location_label",
                "next_stop",
                "eta_minutes",
                "status",
                "network_hint",
                "timestamp",
                "path_preview",
            }
        }
    return state


@app.get("/")
def root() -> dict:
    return {"message": "SmartTransit Resilient Tracker backend is running"}


# Create dummy bus data from ROUTES
def get_all_buses() -> List[dict]:
    buses = []
    for bus_id, route in ROUTES.items():
        # Get current position using the build_bus_state function
        bus_state = build_bus_state(bus_id, route, "good")
        bus = {
            "id": bus_id,
            "name": route["name"],
            "route": route["route_name"],
            "latitude": bus_state["latitude"],
            "longitude": bus_state["longitude"],
            "speed": route["speed"],
            "eta": bus_state["eta_minutes"],
            "status": bus_state["status"],
        }
        buses.append(bus)
    return buses


@app.get("/buses", response_model=List[Bus])
def get_buses() -> List[dict]:
    """Get all buses with their current status"""
    return get_all_buses()


@app.get("/bus/{bus_id}", response_model=Bus)
def get_bus(bus_id: str) -> dict:
    """Get a single bus by ID"""
    if bus_id not in ROUTES:
        raise HTTPException(status_code=404, detail=f"Bus {bus_id} not found")
    
    route = ROUTES[bus_id]
    bus_state = build_bus_state(bus_id, route, "good")
    return {
        "id": bus_id,
        "name": route["name"],
        "route": route["route_name"],
        "latitude": bus_state["latitude"],
        "longitude": bus_state["longitude"],
        "speed": route["speed"],
        "eta": bus_state["eta_minutes"],
        "status": bus_state["status"],
    }


@app.post("/signup")
def signup(payload: SignupPayload) -> dict:
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user = create_user(payload.name, payload.email, payload.password)
    token = create_token(user)
    return {"message": "Signup successful", "token": token, "user": user}


@app.post("/login")
def login(payload: AuthPayload) -> dict:
    user = verify_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_token(user)
    return {"message": "Login successful", "token": token, "user": user}


@app.get("/bus-locations")
def bus_locations(
    bus_id: Optional[str] = None,
    network_tier: str = "good",
    authorization: Optional[str] = Header(default=None),
) -> dict:
    require_auth(authorization)
    simulate_network_delay(network_tier)

    if bus_id and bus_id not in ROUTES:
        raise HTTPException(status_code=404, detail="Bus not found.")

    bus_ids = [bus_id] if bus_id else list(ROUTES.keys())
    buses = [build_bus_state(selected_id, ROUTES[selected_id], network_tier) for selected_id in bus_ids]

    return {
        "network_tier": network_tier,
        "recommended_poll_interval_ms": 5200 if network_tier == "weak" else 2200,
        "buses": buses,
    }


@app.post("/predict-eta")
def predict_eta(payload: ETAPayload, authorization: Optional[str] = Header(default=None)) -> dict:
    require_auth(authorization)
    eta_minutes = eta_service.predict_minutes(
        distance_km=payload.distance_km,
        speed_kmph=payload.speed_kmph,
        historical_delay=payload.historical_delay,
    )
    return {"eta_minutes": eta_minutes}


@app.post("/client-sync")
def client_sync(payload: SyncPayload, authorization: Optional[str] = Header(default=None)) -> dict:
    require_auth(authorization)
    for event in payload.events:
        store_sync_event(event.get("event", "unknown"), json.dumps(event))
    return {"synced": len(payload.events)}
