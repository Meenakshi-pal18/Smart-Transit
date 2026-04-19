# SmartTransit Resilient Tracker

SmartTransit Resilient Tracker is a full-stack demo web app for college transport systems. It combines:

- FastAPI backend
- SQLite user storage
- A scikit-learn ETA prediction model
- A dark, app-like frontend with Leaflet live tracking
- Adaptive polling, sparse GPS smoothing, and offline store-and-forward behavior

## Project Structure

```text
frontend/
  index.html
  login.html
  signup.html
  dashboard.html
  map.html
  style.css
  app.js

backend/
  main.py
  model.py
  database.py

requirements.txt
```

## 1. Install Python Through `py`

If `python` and `pip` do not work in your VS Code terminal, but `py` works, use these commands:

```powershell
py --version
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

## 2. Start The Backend

Open a terminal in VS Code at the project root and run:

```powershell
.venv\Scripts\Activate.ps1
cd backend
py -m uvicorn main:app --reload
```

Backend will start at:

```text
http://127.0.0.1:8000
```

## 3. Start The Frontend

You can run the frontend with either VS Code Live Server or FastAPI static hosting later. The easiest hackathon demo path is:

1. Open the `frontend` folder in VS Code.
2. Right-click `index.html`.
3. Choose `Open with Live Server`.

Typical Live Server address:

```text
http://127.0.0.1:5500/frontend/index.html
```

## 4. Demo Flow

1. Open `signup.html` and create an account.
2. Login with the same email and password.
3. Dashboard loads 8 simulated buses.
4. Search for a bus like `Bus A1`.
5. Open `Track Live`.
6. Watch the bus marker move smoothly on the map.
7. Open DevTools Network tab and throttle to `Slow 3G` to show:
   - `Network Weak` indicator
   - Slower polling
   - Smooth movement without jumping
8. Switch the browser offline to show:
   - Last known state stays visible
   - Predicted motion continues
   - Offline buffer queues events and syncs later

## 5. API Endpoints

### Signup

```http
POST /signup
Content-Type: application/json
```

```json
{
  "name": "Aditi Sharma",
  "email": "aditi@college.edu",
  "password": "secret123"
}
```

### Login

```http
POST /login
Content-Type: application/json
```

```json
{
  "email": "aditi@college.edu",
  "password": "secret123"
}
```

### Fetch buses

```http
GET /bus-locations?network_tier=good
Authorization: Bearer <token>
```

### Predict ETA

```http
POST /predict-eta
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "distance_km": 2.8,
  "speed_kmph": 24,
  "historical_delay": 3.5
}
```

## 6. Hackathon Talking Points

- Reliable under weak internet using adaptive polling
- Uses compressed responses when network is poor
- Smooth interpolation avoids marker jumps
- Sparse GPS updates are handled with forward projection
- ETA is ML-driven using Linear Regression
- Offline events are buffered locally and synced on reconnect

## 7. VS Code Tips

- Install the `Live Server` extension for frontend preview
- Install the `Python` extension by Microsoft
- Use `Ctrl + Shift + P` -> `Python: Select Interpreter` -> choose `.venv`
- Keep one terminal for backend and one browser tab for frontend

## 8. Files To Present During Submission

- Frontend code in `frontend/`
- Backend API in `backend/`
- ETA model logic in `backend/model.py`
- Database and auth helpers in `backend/database.py`
- Setup guide in this `README.md`
