// Base URL of the FastAPI backend.
// In production (Vercel) set VITE_API_URL to the Railway domain; locally it falls back to :8000.
export const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
