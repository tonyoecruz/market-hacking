import axios from "axios";

// In production, this should be an env variable
const API_URL = "http://127.0.0.1:8000";

const api = axios.create({
    baseURL: API_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// Request Interceptor to add Token
api.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
        const token = localStorage.getItem("scope3_token");
        if (token) {
            // Backend (server/main.py) expects 'token' query param for GET requests currently
            if (config.method === 'get' || config.method === 'delete') {
                config.params = { ...config.params, token };
            }
            // For POST/PUT, we might need it in query or body. 
            // Looking at main.py:
            // @app.post("/portfolio/add") ... def add_asset(item: PortfolioItem, token: str):
            // FastAPI expects query param for 'token' argument if it's not in the Pydantic model.
            else {
                config.params = { ...config.params, token };
            }
        }
    }
    return config;
});

export default api;
