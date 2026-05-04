# API Endpoint Reference

Production base URL:

```text
https://backend-api-production-281a.up.railway.app
```

Local development base URL:

```text
http://localhost:8000
```

All JSON examples below use the production base URL. The API currently does not require client authentication. Requests that include a body must send `Content-Type: application/json`.

## Response and Error Conventions

Application-level failures usually return HTTP `200` with a response body where `status` is `"error"` or `"needs_clarification"`. Unexpected server failures return HTTP `500`. Missing conversations return HTTP `404`.

Common response fields:

- `status`: High-level result status. Common values are `"success"`, `"error"`, `"needs_clarification"`, and `"deleted"`.
- `error`: Structured error details when the request could not be completed.
- `conversation_id`: Identifier for a persisted in-memory conversation when using the chat flow.
- `intermediate_steps`: Optional debugging payload containing extracted entities, generated query plan, and query execution outputs.

## GET /health

Checks whether the API process is running.

### Request

```bash
curl https://backend-api-production-281a.up.railway.app/health
```

### Response

```json
{
  "status": "ok",
  "environment": "production",
  "version": "1.0.0"
}
```

### Notes

Use this endpoint for uptime checks, deployment smoke tests, and load balancer health checks. It does not verify database connectivity.

## GET /db-check

Checks whether the API can connect to the configured database.

### Request

```bash
curl https://backend-api-production-281a.up.railway.app/db-check
```

### Response

```json
{
  "db_connected": true
}
```

### Error Behavior

If the database connection fails, the request may return HTTP `500` with a FastAPI error response.

## GET /tables

Lists tables in the database `public` schema.

### Request

```bash
curl https://backend-api-production-281a.up.railway.app/tables
```

### Response

```json
{
  "tables": [
    "games",
    "player_game_stats",
    "players",
    "team_game_stats",
    "teams"
  ]
}
```

### Notes

This is primarily an operational and debugging endpoint. Avoid exposing its output in end-user product UI.

## POST /api/chat

Runs the full conversational chatbot flow. This endpoint supports multi-turn context, ambiguous entity clarification, entity caching, query planning, query execution, and answer synthesis.

Use this endpoint for the frontend chat experience.

### Request Body

```json
{
  "conversation_id": null,
  "message": "What were Steph Curry's last 5 games?",
  "include_steps": false
}
```

### Fields

- `conversation_id`: Optional existing conversation ID. If omitted or `null`, the server creates a new conversation.
- `message`: Required user message.
- `include_steps`: Optional. When `true`, the response includes intermediate entity, planning, and execution details.

### Request

```bash
curl -X POST https://backend-api-production-281a.up.railway.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What were Steph Curry's last 5 games?",
    "include_steps": true
  }'
```

### Success Response

```json
{
  "conversation_id": "6f836f53-7f8f-4d4f-a489-3dd274960e45",
  "message_id": null,
  "status": "success",
  "response": "Steph Curry averaged ...",
  "clarification": null,
  "intermediate_steps": {
    "entities": [
      {
        "status": "resolved",
        "full_name": "Stephen Curry",
        "first_name": "Stephen",
        "last_name": "Curry",
        "id": 201939,
        "surface_text": "Steph Curry",
        "entity_type": "player"
      }
    ],
    "plan": {},
    "execution_result": {}
  },
  "error": null
}
```

### Clarification Response

When the user mentions an ambiguous player or team, the endpoint returns `status: "needs_clarification"` and a clarification object.

```json
{
  "conversation_id": "6f836f53-7f8f-4d4f-a489-3dd274960e45",
  "message_id": null,
  "status": "needs_clarification",
  "response": null,
  "clarification": {
    "clarification_id": "50c2fd98-3b61-4869-8b2c-7b4e8a27eabd",
    "type": "entity_disambiguation",
    "prompt": "I found multiple players matching 'Anthony'. Please select one:",
    "options": [
      {
        "label": "Anthony Davis",
        "value": "Anthony Davis",
        "entity_id": 203076,
        "entity_type": "player"
      }
    ],
    "context": {
      "entity_type": "player",
      "surface_text": "Anthony"
    },
    "created_at": "2026-05-04T12:00:00.000000"
  },
  "intermediate_steps": null,
  "error": null
}
```

To answer the clarification, call `/api/chat` again with the same `conversation_id` and a message containing the selected number or full option name.

### Error Response

```json
{
  "conversation_id": "6f836f53-7f8f-4d4f-a489-3dd274960e45",
  "message_id": null,
  "status": "error",
  "response": null,
  "clarification": null,
  "intermediate_steps": null,
  "error": {
    "message": "Could not find: Example Player"
  }
}
```

## POST /api/query

Runs the full question-answering pipeline without persistent conversation management. This endpoint extracts entities, resolves them, plans a query, executes it, and synthesizes a natural-language answer.

Use this endpoint for stateless one-shot questions.

### Request Body

```json
{
  "message": "How many threes did LeBron make against the Cavs?",
  "include_steps": false
}
```

### Fields

- `message`: Required natural-language basketball question.
- `include_steps`: Optional. When `true`, includes intermediate details useful for debugging.

### Request

```bash
curl -X POST https://backend-api-production-281a.up.railway.app/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many threes did LeBron make against the Cavs?",
    "include_steps": true
  }'
```

### Success Response

```json
{
  "status": "success",
  "response": "LeBron James made ...",
  "clarification": null,
  "intermediate_steps": {
    "entities": [
      {
        "status": "resolved",
        "full_name": "LeBron James",
        "first_name": "LeBron",
        "last_name": "James",
        "id": 2544,
        "surface_text": "LeBron",
        "entity_type": "player"
      },
      {
        "status": "resolved",
        "team": "Cleveland Cavaliers",
        "id": 1610612739,
        "city": "Cleveland",
        "name": "Cavaliers",
        "abbreviation": "CLE",
        "surface_text": "Cavs",
        "entity_type": "team"
      }
    ],
    "plan": {},
    "execution_result": {}
  },
  "error": null,
  "resolved_entities": [],
  "plan": {},
  "execution_metadata": {
    "step_count": 1,
    "result_row_count": 1
  }
}
```

### Error and Clarification Behavior

`/api/query` may return the same application-level statuses as `/api/chat`, including `"error"` and `"needs_clarification"`. Because it is stateless, use `/api/chat` when you need a complete clarification follow-up flow.

## POST /api/resolve-entities

Extracts and resolves NBA player and team mentions from a message. This endpoint stops after entity resolution and returns the resolved entity dictionaries without planning or executing a stats query.

Use this endpoint when a client needs IDs for players or teams before calling another system.

### Request Body

```json
{
  "message": "How many threes did LeBron make against the Cavs and Dubs?",
  "conversation_id": null
}
```

### Fields

- `message`: Required text to scan for NBA player and team mentions.
- `conversation_id`: Optional existing conversation ID. When provided, the resolver can use cached entities from that conversation.

### Request

```bash
curl -X POST https://backend-api-production-281a.up.railway.app/api/resolve-entities \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many threes did LeBron make against the Cavs and Dubs?"
  }'
```

### Success Response

```json
{
  "status": "success",
  "resolved_entities": [
    {
      "status": "resolved",
      "full_name": "LeBron James",
      "first_name": "LeBron",
      "last_name": "James",
      "id": 2544,
      "surface_text": "LeBron",
      "entity_type": "player"
    },
    {
      "status": "resolved",
      "team": "Cleveland Cavaliers",
      "id": 1610612739,
      "city": "Cleveland",
      "name": "Cavaliers",
      "abbreviation": "CLE",
      "surface_text": "Cavs",
      "entity_type": "team"
    },
    {
      "status": "resolved",
      "team": "Golden State Warriors",
      "id": 1610612744,
      "city": "Golden State",
      "name": "Warriors",
      "abbreviation": "GSW",
      "surface_text": "Dubs",
      "entity_type": "team"
    }
  ],
  "conversation_id": null,
  "error": null
}
```

### Ambiguous Entity Response

This endpoint returns ambiguous entities directly in `resolved_entities`; it does not create a clarification prompt.

```json
{
  "status": "success",
  "resolved_entities": [
    {
      "status": "ambiguous",
      "players": [
        {
          "id": 203076,
          "full_name": "Anthony Davis",
          "first_name": "Anthony",
          "last_name": "Davis"
        },
        {
          "id": 1630162,
          "full_name": "Anthony Edwards",
          "first_name": "Anthony",
          "last_name": "Edwards"
        }
      ],
      "surface_text": "Anthony",
      "entity_type": "player"
    }
  ],
  "conversation_id": null,
  "error": null
}
```

### Error Response

```json
{
  "status": "error",
  "resolved_entities": null,
  "conversation_id": null,
  "error": {
    "message": "Failed to extract entities.",
    "details": {
      "status": "failed",
      "error": "JSON parsing failed..."
    }
  }
}
```

### HTTP 404

If `conversation_id` is provided but not found:

```json
{
  "detail": "Conversation not found"
}
```

## GET /api/conversations/{conversation_id}

Returns the full stored conversation object for a conversation ID.

### Request

```bash
curl https://backend-api-production-281a.up.railway.app/api/conversations/6f836f53-7f8f-4d4f-a489-3dd274960e45
```

### Response

```json
{
  "conversation_id": "6f836f53-7f8f-4d4f-a489-3dd274960e45",
  "created_at": "2026-05-04T12:00:00.000000",
  "updated_at": "2026-05-04T12:05:00.000000",
  "messages": [
    {
      "message_id": "96d4e5f8-3991-4f0e-8a70-60c21a064af0",
      "conversation_id": "6f836f53-7f8f-4d4f-a489-3dd274960e45",
      "role": "user",
      "content": "What are Curry's stats?",
      "timestamp": "2026-05-04T12:00:00.000000",
      "intermediate_steps": null,
      "metadata": {}
    }
  ],
  "resolved_entities": {},
  "pending_clarification": null,
  "metadata": {}
}
```

### HTTP 404

```json
{
  "detail": "Conversation not found"
}
```

### Notes

Conversations are stored in memory and expire after the configured TTL. They are not durable across process restarts unless the storage implementation changes.

## DELETE /api/conversations/{conversation_id}

Deletes a stored conversation.

### Request

```bash
curl -X DELETE https://backend-api-production-281a.up.railway.app/api/conversations/6f836f53-7f8f-4d4f-a489-3dd274960e45
```

### Response

```json
{
  "status": "deleted",
  "conversation_id": "6f836f53-7f8f-4d4f-a489-3dd274960e45"
}
```

### HTTP 404

```json
{
  "detail": "Conversation not found"
}
```

## OpenAPI Documentation

FastAPI also serves generated OpenAPI documentation:

```text
https://backend-api-production-281a.up.railway.app/docs
```

The generated docs are useful for live schema inspection and manual requests. This document is the source of human-readable endpoint behavior, production examples, and operational guidance.
