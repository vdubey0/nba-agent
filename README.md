# NBA Stats Chatbot

An intelligent chatbot that answers questions about NBA statistics using natural language processing and a PostgreSQL database.

## 🌟 Features

- **Natural Language Queries**: Ask questions in plain English about NBA players, teams, and games
- **Conversational Context**: Multi-turn conversations with entity resolution caching
- **Ambiguous Entity Clarification**: Automatically handles ambiguous references (e.g., "Anthony" → Anthony Davis or Anthony Edwards)
- **Intermediate Steps**: Optional display of entity extraction, query planning, and execution details
- **Modern UI**: Clean, responsive React interface with real-time chat
- **Robust Error Handling**: Automatic retry logic with error context for LLM calls

## 🏗️ Architecture

### Backend (FastAPI + PostgreSQL)
- **Entity Extraction**: LLM-powered extraction of players, teams, and time periods
- **Query Planning**: Intelligent query plan generation based on question type
- **Query Execution**: SQL query execution with result aggregation
- **Answer Synthesis**: Natural language answer generation from query results

### Frontend (React + Vite)
- **Chat Interface**: Real-time messaging with markdown support
- **Clarification UI**: Interactive entity disambiguation
- **Steps Viewer**: Collapsible intermediate steps display
- **Responsive Design**: Mobile-friendly with Tailwind CSS

## 📋 Prerequisites

- Python 3.9+
- Node.js 20+
- PostgreSQL 14+
- OpenAI API key

## 🚀 Quick Start

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and database credentials

# Initialize database
python app/reset_db.py

# Ingest NBA data
python ingest/backfill.py

# Start the backend server
uvicorn app.main:app --reload --port 8000
```

The backend API will be available at http://localhost:8000

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env if needed (default: VITE_API_URL=http://localhost:8000)

# Start the development server
npm run dev
```

The frontend will be available at http://localhost:5173

## 💬 Usage

### Example Questions

**Player Stats:**
- "What are Stephen Curry's stats this season?"
- "How many points did LeBron James score in his last game?"
- "Show me Anthony Davis's rebounds and assists"

**Team Performance:**
- "How did the Lakers do in their last game?"
- "What are the Warriors' stats this season?"

**Comparisons:**
- "Compare LeBron James and Kevin Durant's scoring"
- "Who scored more points, Curry or Harden?"

**Ambiguous Queries:**
- "How many points did Anthony score?" → System will ask: Anthony Davis or Anthony Edwards?
- "What are Curry's stats?" → If context exists, uses previous reference

### Clarification Flow

1. Ask a question with an ambiguous entity
2. System presents numbered options
3. Select by clicking or typing the number
4. System continues with your selection

### Viewing Intermediate Steps

1. Toggle "Show intermediate steps" in the header
2. Click the dropdown arrow on any assistant message
3. View:
   - Extracted entities
   - Query plan
   - Execution results

## 🛠️ Development

### Backend Development

```bash
cd backend
source .venv/bin/activate

# Run tests
pytest

# Interactive chat (CLI)
python interactive_chat.py

# Check database
python -c "from app.db import engine; print(engine.url)"
```

### Frontend Development

```bash
cd frontend

# Development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## 📁 Project Structure

```
nba-agent/
├── backend/
│   ├── app/
│   │   ├── models/           # Database models
│   │   ├── orchestrator/     # LLM orchestration
│   │   ├── query/            # Query execution
│   │   ├── utils/            # Utilities (retry, clarification)
│   │   ├── chat_flow.py      # Conversational flow
│   │   ├── main.py           # FastAPI app
│   │   └── db.py             # Database connection
│   ├── ingest/               # Data ingestion scripts
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── services/         # API client
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── .env
├── ARCHITECTURE.md           # Detailed architecture docs
├── IMPLEMENTATION_PLAN.md    # Implementation guide
└── README.md                 # This file
```

## 🔧 Configuration

### Backend Environment Variables

```env
# OpenAI
OPENAI_API_KEY=your_api_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/nba_stats

# Optional
LOG_LEVEL=INFO
```

### Frontend Environment Variables

```env
VITE_API_URL=http://localhost:8000
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 📊 API Endpoints

### Chat Endpoint
```
POST /api/chat
{
  "conversation_id": "uuid-or-null",
  "message": "What are Curry's stats?",
  "include_steps": true
}
```

### Health Check
```
GET /health
```

### Conversation Management
```
GET /api/conversations/{id}
DELETE /api/conversations/{id}
```

## 🐛 Troubleshooting

### Backend Issues

**Database Connection Error:**
- Check PostgreSQL is running
- Verify DATABASE_URL in .env
- Ensure database exists

**OpenAI API Error:**
- Verify OPENAI_API_KEY is set
- Check API quota and billing

**Import Errors:**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

### Frontend Issues

**CORS Error:**
- Backend CORS is configured for localhost:5173
- Check backend is running
- Verify VITE_API_URL in .env

**Build Errors:**
- Clear node_modules: `rm -rf node_modules package-lock.json`
- Reinstall: `npm install`

## 📚 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system architecture
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Implementation guide
- [QUICK_START.md](QUICK_START.md) - Quick reference guide
- [backend/TEST_INSTRUCTIONS.md](backend/TEST_INSTRUCTIONS.md) - Testing guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- NBA Stats API for data
- OpenAI for LLM capabilities
- FastAPI and React communities

## 📧 Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

---

Built with ❤️ for NBA stats enthusiasts