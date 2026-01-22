#!/bin/bash
echo "🚀 Starting Scope3 SaaS System..."

# Start Backend
echo "📡 Launching Backend (FastAPI)..."
cd server
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start Client
echo "💻 Launching Frontend (Next.js)..."
cd client
npm run dev &
FRONTEND_PID=$!
cd ..

echo "✅ System Online!"
echo "➡️  Frontend: http://localhost:3000"
echo "➡️  Backend:  http://localhost:8000/docs"
echo "Press CTRL+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT

wait
