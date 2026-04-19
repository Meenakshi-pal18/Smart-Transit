const API_BASE = "http://127.0.0.1:8000";
const STORAGE_KEYS = {
  user: "smartTransitUser",
  token: "smartTransitToken",
  network: "smartTransitNetworkState",
  syncQueue: "smartTransitSyncQueue"
};

const appState = {
  buses: [],
  pollingMs: 2500,
  networkQuality: "good",
  lastBusSnapshot: null,
  map: null,
  marker: null,
  routeLine: null,
  smoothingFrame: null,
  currentAnimatedPoint: null
};

document.addEventListener("DOMContentLoaded", () => {
  bindAuthForms();
  bindDashboard();
  bindMapPage();
  bindLogout();
  installNetworkListeners();
  updateNetworkUI();
  flushOfflineQueue();
});

function bindAuthForms() {
  const signupForm = document.getElementById("signupForm");
  const loginForm = document.getElementById("loginForm");

  if (signupForm) {
    signupForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const messageNode = document.getElementById("signupMessage");
      setMessage(messageNode, "Creating account...", false);
      const formData = new FormData(signupForm);

      try {
        const response = await resilientFetch("/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: formData.get("name"),
            email: formData.get("email"),
            password: formData.get("password")
          })
        });

        cacheSession(response);
        setMessage(messageNode, "Account created. Redirecting to dashboard...", true);
        setTimeout(() => {
          window.location.href = "dashboard.html";
        }, 700);
      } catch (error) {
        setMessage(messageNode, error.message, false);
      }
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const messageNode = document.getElementById("loginMessage");
      setMessage(messageNode, "Checking credentials...", false);
      const formData = new FormData(loginForm);

      try {
        const response = await resilientFetch("/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: formData.get("email"),
            password: formData.get("password")
          })
        });

        cacheSession(response);
        setMessage(messageNode, "Login successful. Opening dashboard...", true);
        setTimeout(() => {
          window.location.href = "dashboard.html";
        }, 500);
      } catch (error) {
        setMessage(messageNode, error.message, false);
      }
    });
  }
}

function bindDashboard() {
  const busGrid = document.getElementById("busGrid");
  if (!busGrid) {
    return;
  }

  requireSession();
  const searchInput = document.getElementById("busSearch");

  const fetchAndRender = async () => {
    setSyncBadge("Refreshing buses");

    try {
      const payload = await fetchBusLocations();
      appState.buses = payload.buses;
      renderBusCards(payload.buses, searchInput.value);
      appState.pollingMs = payload.recommended_poll_interval_ms || appState.pollingMs;
      setSyncBadge(`Live every ${Math.round(appState.pollingMs / 1000)}s`);
    } catch (error) {
      renderBusCards(appState.buses, searchInput.value);
      setSyncBadge("Using cached data");
    }
  };

  searchInput.addEventListener("input", () => renderBusCards(appState.buses, searchInput.value));
  fetchAndRender();
  setInterval(fetchAndRender, 12000);
}

function bindMapPage() {
  const mapElement = document.getElementById("map");
  if (!mapElement) {
    return;
  }

  requireSession();
  const busId = new URLSearchParams(window.location.search).get("bus");
  if (!busId) {
    window.location.href = "dashboard.html";
    return;
  }

  initializeMap();
  startTracking(busId);
}

function bindLogout() {
  const logoutButton = document.getElementById("logoutButton");
  if (!logoutButton) {
    return;
  }

  logoutButton.addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEYS.user);
    localStorage.removeItem(STORAGE_KEYS.token);
  });
}

function requireSession() {
  if (!localStorage.getItem(STORAGE_KEYS.token)) {
    window.location.href = "login.html";
  }
}

function cacheSession(payload) {
  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(payload.user));
  localStorage.setItem(STORAGE_KEYS.token, payload.token);
}

function setMessage(node, text, success) {
  if (!node) {
    return;
  }

  node.textContent = text;
  node.classList.toggle("success", success);
  node.classList.toggle("error", !success);
}

async function fetchBusLocations(busId = null) {
  const networkQuality = determineNetworkQuality();
  const query = new URLSearchParams({ network_tier: networkQuality });

  if (busId) {
    query.set("bus_id", busId);
  }

  const start = performance.now();
  const payload = await resilientFetch(`/bus-locations?${query.toString()}`);
  const latency = performance.now() - start;
  updateAdaptivePolling(latency, networkQuality);
  localStorage.setItem(STORAGE_KEYS.network, JSON.stringify({
    quality: appState.networkQuality,
    pollingMs: appState.pollingMs,
    latency
  }));
  return payload;
}

function renderBusCards(buses, term = "") {
  const grid = document.getElementById("busGrid");
  if (!grid) {
    return;
  }

  const normalizedTerm = term.trim().toLowerCase();
  const filtered = buses.filter((bus) => {
    const haystack = `${bus.name} ${bus.route_name} ${bus.next_stop}`.toLowerCase();
    return haystack.includes(normalizedTerm);
  });

  if (!filtered.length) {
    grid.innerHTML = `<article class="dashboard-card"><h3>No matching buses</h3><p class="dashboard-meta">Try another search term.</p></article>`;
    return;
  }

  grid.innerHTML = filtered.map((bus) => `
    <article class="dashboard-card">
      <div class="dashboard-actions">
        <span class="mini-chip">${bus.status}</span>
        <span class="mini-chip">${bus.network_hint}</span>
      </div>
      <div>
        <h3>${bus.name}</h3>
        <p class="dashboard-meta">${bus.route_name}</p>
      </div>
      <div class="dashboard-meta">
        <span>Next stop: ${bus.next_stop}</span>
        <span>ETA: ${bus.eta_minutes} mins</span>
      </div>
      <a class="button button-primary" href="map.html?bus=${encodeURIComponent(bus.id)}">Track Live</a>
    </article>
  `).join("");
}

function initializeMap() {
  appState.map = L.map("map", {
    zoomControl: true,
    attributionControl: false
  }).setView([12.9716, 77.5946], 15);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19
  }).addTo(appState.map);

  const busIcon = L.divIcon({
    className: "custom-bus-icon",
    html: `<div style="width:18px;height:18px;border-radius:50%;background:#16c2a3;box-shadow:0 0 0 10px rgba(22,194,163,0.18);border:2px solid #eaf9f4;"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });

  appState.marker = L.marker([12.9716, 77.5946], { icon: busIcon }).addTo(appState.map);
  appState.routeLine = L.polyline([], {
    color: "#16c2a3",
    weight: 5,
    opacity: 0.68
  }).addTo(appState.map);
}

async function startTracking(busId) {
  const titleNode = document.getElementById("mapTitle");

  const loop = async () => {
    if (!navigator.onLine && appState.lastBusSnapshot) {
      setSyncBadge("Offline prediction");
      const predicted = projectForward(appState.lastBusSnapshot);
      consumeTrackingPayload(predicted, true);
      queueOfflineSync({ event: "offline_projection", bus_id: busId, ts: Date.now() });
      scheduleNext(loop, Math.max(appState.pollingMs, 5000));
      return;
    }

    try {
      setSyncBadge("Fetching live position");
      const payload = await fetchBusLocations(busId);
      const bus = payload.buses[0];
      appState.lastBusSnapshot = bus;
      consumeTrackingPayload(bus, false);
      titleNode.textContent = `${bus.name} Live Tracking`;
      scheduleNext(loop, appState.pollingMs);
    } catch (error) {
      if (appState.lastBusSnapshot) {
        consumeTrackingPayload(projectForward(appState.lastBusSnapshot), true);
        setSyncBadge("Signal weak - smoothing with cached path");
      } else {
        setSyncBadge("Retrying connection");
      }
      scheduleNext(loop, Math.max(appState.pollingMs, 4500));
    }
  };

  loop();
}

function consumeTrackingPayload(bus, isPredicted) {
  document.getElementById("busName").textContent = bus.name;
  document.getElementById("liveLocation").textContent = `${bus.current_location_label}${isPredicted ? " - predicted" : ""}`;
  document.getElementById("nextStop").textContent = bus.next_stop;
  document.getElementById("etaValue").textContent = `${bus.eta_minutes} mins`;
  document.getElementById("pollingInfo").textContent = `Polling every ${Math.round(appState.pollingMs / 1000)}s in ${appState.networkQuality} network mode.`;
  document.getElementById("bufferInfo").textContent = `${getOfflineQueue().length} unsent sync packets`;

  smoothMoveMarker([bus.latitude, bus.longitude], bus.path_preview || []);
}

function smoothMoveMarker(targetLatLng, previewPath) {
  if (!appState.currentAnimatedPoint) {
    appState.currentAnimatedPoint = [...targetLatLng];
    appState.marker.setLatLng(targetLatLng);
    appState.map.setView(targetLatLng, 15, { animate: true });
  }

  if (previewPath.length) {
    appState.routeLine.setLatLngs(previewPath.map((point) => [point.lat, point.lng]));
  }

  const start = [...appState.currentAnimatedPoint];
  const end = [...targetLatLng];
  const duration = Math.min(Math.max(appState.pollingMs - 250, 1200), 4800);
  const startedAt = performance.now();

  if (appState.smoothingFrame) {
    cancelAnimationFrame(appState.smoothingFrame);
  }

  const animate = (now) => {
    const progress = Math.min((now - startedAt) / duration, 1);
    const eased = cubicEaseInOut(progress);
    const lat = lerp(start[0], end[0], eased);
    const lng = lerp(start[1], end[1], eased);
    appState.currentAnimatedPoint = [lat, lng];
    appState.marker.setLatLng(appState.currentAnimatedPoint);
    appState.map.panTo(appState.currentAnimatedPoint, { animate: false });

    if (progress < 1) {
      appState.smoothingFrame = requestAnimationFrame(animate);
    }
  };

  appState.smoothingFrame = requestAnimationFrame(animate);
}

function projectForward(bus) {
  const delta = Math.max((Date.now() - new Date(bus.timestamp).getTime()) / 1000, 0);
  const route = bus.path_preview || [];
  if (route.length < 2) {
    return bus;
  }

  const nextPoint = route[Math.min(1, route.length - 1)];
  const factor = Math.min(delta / Math.max(appState.pollingMs / 1000, 1), 0.35);

  return {
    ...bus,
    latitude: lerp(bus.latitude, nextPoint.lat, factor),
    longitude: lerp(bus.longitude, nextPoint.lng, factor),
    current_location_label: "Projected from last known state"
  };
}

function determineNetworkQuality() {
  if (!navigator.onLine) {
    appState.networkQuality = "offline";
    return "offline";
  }

  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (!connection) {
    return appState.networkQuality;
  }

  const effectiveType = connection.effectiveType || "4g";
  if (effectiveType.includes("2g") || connection.rtt > 600 || connection.downlink < 1.2) {
    appState.networkQuality = "weak";
  } else {
    appState.networkQuality = "good";
  }

  return appState.networkQuality;
}

function updateAdaptivePolling(latency, networkQuality) {
  if (networkQuality === "offline") {
    appState.pollingMs = 6000;
    return;
  }

  if (latency > 1300 || networkQuality === "weak") {
    appState.networkQuality = "weak";
    appState.pollingMs = 5200;
  } else if (latency > 700) {
    appState.networkQuality = "moderate";
    appState.pollingMs = 3800;
  } else {
    appState.networkQuality = "good";
    appState.pollingMs = 2200;
  }

  updateNetworkUI(latency);
}

function updateNetworkUI(latency = 0) {
  const badge = document.getElementById("networkBadge");
  if (!badge) {
    return;
  }

  const quality = determineNetworkQuality();
  badge.classList.remove("weak", "offline");

  if (quality === "offline") {
    badge.textContent = "Offline";
    badge.classList.add("offline");
  } else if (quality === "weak") {
    badge.textContent = `Network Weak${latency ? ` - ${Math.round(latency)} ms` : ""}`;
    badge.classList.add("weak");
  } else if (quality === "moderate") {
    badge.textContent = `Network Recovering${latency ? ` - ${Math.round(latency)} ms` : ""}`;
  } else {
    badge.textContent = `Network Stable${latency ? ` - ${Math.round(latency)} ms` : ""}`;
  }
}

function setSyncBadge(text) {
  const badge = document.getElementById("syncBadge");
  if (badge) {
    badge.textContent = text;
  }
}

async function resilientFetch(path, options = {}) {
  const authHeaders = localStorage.getItem(STORAGE_KEYS.token)
    ? { Authorization: `Bearer ${localStorage.getItem(STORAGE_KEYS.token)}` }
    : {};

  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...authHeaders,
        ...(options.headers || {})
      }
    });
  } catch (error) {
    const isNetworkFailure = error instanceof TypeError && error.message.includes("Failed to fetch");
    const message = isNetworkFailure
      ? "Could not connect to the server. Please make sure the backend is running on http://127.0.0.1:8000."
      : "Network error. Please try again.";

    if (isNetworkFailure) {
      window.alert("Server is not running. Start the backend on http://127.0.0.1:8000 and try again.");
    }

    throw new Error(message);
  }

  if (!response.ok) {
    let message = "Request failed";
    try {
      const errorData = await response.json();
      message = errorData.detail || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.json();
}

function installNetworkListeners() {
  window.addEventListener("online", () => {
    updateNetworkUI();
    flushOfflineQueue();
  });

  window.addEventListener("offline", () => {
    updateNetworkUI();
    setSyncBadge("Offline mode enabled");
  });

  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (connection) {
    connection.addEventListener("change", () => updateNetworkUI());
  }
}

function queueOfflineSync(payload) {
  const queue = getOfflineQueue();
  queue.push(payload);
  localStorage.setItem(STORAGE_KEYS.syncQueue, JSON.stringify(queue.slice(-40)));
}

function getOfflineQueue() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.syncQueue) || "[]");
  } catch (error) {
    return [];
  }
}

async function flushOfflineQueue() {
  const queue = getOfflineQueue();
  if (!queue.length || !navigator.onLine) {
    return;
  }

  try {
    await resilientFetch("/client-sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: queue })
    });
    localStorage.setItem(STORAGE_KEYS.syncQueue, "[]");
  } catch (error) {
    setSyncBadge("Waiting to sync offline events");
  }
}

function scheduleNext(callback, delay) {
  window.setTimeout(callback, delay);
}

function lerp(start, end, progress) {
  return start + (end - start) * progress;
}

function cubicEaseInOut(x) {
  return x < 0.5
    ? 4 * x * x * x
    : 1 - Math.pow(-2 * x + 2, 3) / 2;
}
