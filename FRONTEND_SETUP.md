# Frontend Setup Guide

This guide will help you get the NBA Stats Chatbot frontend up and running.

## Quick Start

### Option 1: Use the Startup Script (Recommended)

```bash
# Make sure you're in the project root directory
./start.sh
```

This will start both the backend and frontend servers automatically.

### Option 2: Manual Setup

#### 1. Start the Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

#### 2. Start the Frontend (in a new terminal)

```bash
cd frontend
npm run dev
```

## Access the Application

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Features to Try

### 1. Basic Questions
- "What are Stephen Curry's stats this season?"
- "How many points did LeBron score in his last game?"

### 2. Ambiguous Entity Clarification
- Ask: "How many points did Anthony score?"
- The system will present options (Anthony Davis, Anthony Edwards)
- Select one by clicking or typing the number

### 3. Intermediate Steps
- Toggle "Show intermediate steps" in the header
- Ask any question
- Click the dropdown arrow on the response to see:
  - Entity extraction
  - Query planning
  - Execution results

### 4. Multi-turn Conversations
- Ask: "What are Steph Curry's stats?"
- Then ask: "How does Curry compare to LeBron?"
- The system remembers "Curry" refers to "Steph Curry"

## UI Components

### Chat Interface
- **Message Input**: Type your question and press Enter
- **Message History**: Scrollable conversation history
- **Clear Chat**: Reset the conversation
- **Show Steps Toggle**: Enable/disable intermediate steps display

### Message Types
- **User Messages**: Blue bubbles on the right
- **Assistant Messages**: Gray bubbles on the left
- **Clarification Prompts**: Interactive buttons for disambiguation
- **Error Messages**: Red-bordered boxes with error details
- **Loading Indicator**: Animated dots while processing

## Troubleshooting

### Frontend Won't Start

**Error: `Cannot find module`**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**Error: Port 5173 already in use**
```bash
# Kill the process using the port
lsof -ti:5173 | xargs kill -9
# Or use a different port
npm run dev -- --port 3000
```

### Backend Connection Issues

**Error: Network Error or CORS**
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify `.env` file has correct API URL
3. Check browser console for specific errors

**Error: 404 Not Found**
- Ensure backend has the `/api/chat` endpoint
- Check backend logs for errors
- Verify you're using the updated `backend/app/main.py`

### Styling Issues

**Tailwind classes not working**
```bash
cd frontend
npm install -D tailwindcss postcss autoprefixer
```

**CSS not loading**
- Check `src/index.css` has Tailwind directives
- Restart the dev server

## Development Tips

### Hot Reload
Both frontend and backend support hot reload:
- Frontend: Changes to `.jsx` files reload automatically
- Backend: Changes to `.py` files reload automatically (with `--reload` flag)

### Browser DevTools
- Open DevTools (F12 or Cmd+Option+I)
- Check Console for JavaScript errors
- Check Network tab for API calls
- Use React DevTools extension for component inspection

### API Testing
Test the backend API directly:
```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are Curry stats?", "include_steps": true}'
```

## Building for Production

### Frontend Build
```bash
cd frontend
npm run build
```

The build output will be in `frontend/dist/`

### Serve Production Build
```bash
cd frontend
npm run preview
```

## Environment Variables

### Frontend `.env`
```env
VITE_API_URL=http://localhost:8000
```

For production, update to your production API URL:
```env
VITE_API_URL=https://api.yourdomain.com
```

## Next Steps

1. ✅ Start both servers
2. ✅ Open http://localhost:5173
3. ✅ Try the example questions
4. ✅ Test clarification flow with "Anthony"
5. ✅ Enable intermediate steps
6. ✅ Test multi-turn conversations

## Support

- Check the main [README.md](README.md) for full documentation
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- See [backend/TEST_INSTRUCTIONS.md](backend/TEST_INSTRUCTIONS.md) for testing

## Screenshots

### Main Chat Interface
- Clean, modern design
- Real-time message updates
- Markdown support for formatted responses

### Clarification UI
- Numbered options for disambiguation
- Click or type to select
- Seamless continuation after selection

### Intermediate Steps
- Collapsible details
- Entity extraction results
- Query plan visualization
- Execution results in JSON

---

Happy chatting! 🏀