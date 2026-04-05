# NBA Stats Chatbot - Frontend

A modern React-based chat interface for the NBA Stats Chatbot.

## Features

- 💬 Real-time chat interface
- 🔄 Multi-turn conversations with context
- ❓ Ambiguous entity clarification
- 📊 Optional intermediate steps display
- 🎨 Clean, responsive UI with Tailwind CSS
- ⚡ Fast and lightweight with Vite

## Prerequisites

- Node.js 20.x or higher
- npm or yarn
- Backend API running on http://localhost:8000

## Installation

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file (or copy from `.env.example`):
```bash
cp .env.example .env
```

3. Update the `.env` file with your backend API URL:
```
VITE_API_URL=http://localhost:8000
```

## Development

Start the development server:
```bash
npm run dev
```

The app will be available at http://localhost:5173

## Building for Production

Build the production bundle:
```bash
npm run build
```

Preview the production build:
```bash
npm run preview
```

## Usage

### Basic Chat
1. Type your question in the input box
2. Press Enter or click Send
3. View the response from the chatbot

### Example Questions
- "What are Stephen Curry's stats this season?"
- "Who scored the most points in the last Lakers game?"
- "How many rebounds did Anthony Davis get?"
- "Compare LeBron James and Kevin Durant's scoring"

### Clarification Flow
If your question contains an ambiguous entity (e.g., "Anthony" could be Anthony Davis or Anthony Edwards):
1. The chatbot will present numbered options
2. Click on an option or type the number
3. The chatbot will continue with your selected entity

### Intermediate Steps
Toggle "Show intermediate steps" in the header to see:
- Entity extraction results
- Query planning details
- Execution results

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Chat.jsx          # Main chat container
│   │   ├── Message.jsx        # Individual message component
│   │   └── MessageInput.jsx   # Input component
│   ├── services/
│   │   └── api.js             # API client
│   ├── App.jsx                # Root component
│   ├── index.css              # Global styles with Tailwind
│   └── main.jsx               # Entry point
├── public/                    # Static assets
├── .env                       # Environment variables
├── tailwind.config.js         # Tailwind configuration
├── vite.config.js             # Vite configuration
└── package.json               # Dependencies
```

## Technologies

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Axios** - HTTP client
- **React Markdown** - Markdown rendering

## Troubleshooting

### CORS Errors
Make sure the backend has CORS configured to allow requests from `http://localhost:5173`

### API Connection Issues
1. Verify the backend is running on the correct port
2. Check the `VITE_API_URL` in your `.env` file
3. Ensure the backend health endpoint returns OK: `curl http://localhost:8000/health`

### Build Errors
If you encounter build errors, try:
```bash
rm -rf node_modules package-lock.json
npm install
```

## License

MIT
