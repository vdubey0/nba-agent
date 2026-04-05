#!/bin/bash

# NBA Stats Chatbot - Startup Script
# This script starts both the backend and frontend servers

echo "🏀 Starting NBA Stats Chatbot..."
echo ""

# Check if backend virtual environment exists
if [ ! -d "backend/.venv" ]; then
    echo "❌ Backend virtual environment not found!"
    echo "Please run: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if frontend node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ Frontend dependencies not installed!"
    echo "Please run: cd frontend && npm install"
    exit 1
fi

# Check if .env files exist
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Backend .env file not found. Creating from example..."
    cp backend/.env.example backend/.env 2>/dev/null || echo "Please create backend/.env with your configuration"
fi

if [ ! -f "frontend/.env" ]; then
    echo "⚠️  Frontend .env file not found. Creating from example..."
    cp frontend/.env.example frontend/.env 2>/dev/null || echo "VITE_API_URL=http://localhost:8000" > frontend/.env
fi

echo "✅ Starting backend server on http://localhost:8000..."
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

echo "✅ Starting frontend server on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "🎉 Both servers are starting!"
echo ""
echo "📍 Backend API: http://localhost:8000"
echo "📍 Frontend UI: http://localhost:5173"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

# Trap Ctrl+C and call cleanup
trap cleanup INT TERM

# Wait for both processes
wait

# Made with Bob
