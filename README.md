# chatgpt-web-voice

Self-hosted **ChatGPT Web voice gateway**.

## Live demo

- **Implemented product**: [https://voice.peekcart.com/](https://voice.peekcart.com/)

This repository open-sources the **voice-only** stack used by that deployment:
WebRTC SDP proxy, in-call text/image relay, captions, and auto-interrupt.

Browser owns WebRTC audio.  
This service only:

- picks a web `access_token`
- exchanges SDP via `POST https://chatgpt.com/realtime/wm`
- uploads images for in-call `relay_message`
- binds `voice_session_id -> token`

No chat2 / admin / register / image-gen stack is included.

## Features

- Realtime voice call (wingman / advanced / standard)
- In-call text via DataChannel `relay_message`
- In-call image via `/api/voice/upload-image` + `sediment://file_id`
- Auto barge-in interrupt (`action_request: stop_speaking`)
- Captions from `chat_message_delta`
- Voice session token binding

## Quick start

### 1) Install

```bash
python -m venv .venv
# Windows
.venv\Scriptsctivate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2) Configure accounts

```bash
cp data/accounts.example.json data/accounts.json
# put your ChatGPT web access_token into data/accounts.json
```

```bash
cp .env.example .env
# set VOICE_AUTH_KEY
```

### 3) Run

```bash
export VOICE_AUTH_KEY=change-me
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

- `http://127.0.0.1:8000/voice.html`

Use the same key in the page advanced settings.

### Docker

```bash
cp data/accounts.example.json data/accounts.json
cp .env.example .env
docker compose up --build
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/voice/health` | health |
| POST | `/api/voice/session` | offer SDP -> answer SDP |
| POST | `/api/voice/upload-image` | upload image, return `file_id` |
| POST | `/api/voice/session/release` | unbind voice session |

Auth:

```http
Authorization: Bearer <VOICE_AUTH_KEY>
```

## Architecture

```text
Browser (static/voice.html)
  mic + RTCPeerConnection + DataChannel(oai-events)
        |
        | /api/voice/session
        | /api/voice/upload-image
        v
Gateway (this repo)
  account pool + optional proxy + curl_cffi chrome TLS
        |
        v
chatgpt.com
  /realtime/wm + Azure WebRTC media + files upload
```

## In-call text / image protocol

Envelope:

```json
{ "type": "data_message", "data": "<json string>" }
```

Text:

```json
{
  "type": "relay_message",
  "payload": {
    "type": "relay_message",
    "message": {
      "id": "uuid",
      "author": { "role": "user" },
      "create_time": 1710000000.0,
      "content": { "content_type": "text", "parts": ["hello"] },
      "metadata": { "serialization_metadata": { "custom_symbol_offsets": [] } },
      "clientMetadata": { "isOptimistic": true }
    }
  }
}
```

Interrupt:

```json
{ "type": "action_request", "payload": { "action": "stop_speaking" } }
```

## Environment

| Env | Default | Meaning |
|---|---|---|
| `VOICE_AUTH_KEY` | `change-me` | gateway auth key |
| `VOICE_ACCOUNTS_FILE` | `./data/accounts.json` | account pool |
| `VOICE_HTTP_PROXY` | empty | optional egress proxy |
| `VOICE_SKIP_SSL_VERIFY` | `true` | skip TLS verify |
| `VOICE_IMPERSONATE` | `chrome136` | curl_cffi impersonate |

## Security

- Do **not** commit real `accounts.json` / tokens
- Frontend only holds gateway key, never OpenAI web token
- Use HTTPS in production

## License / disclaimer

Research / self-hosted gateway.  
Requires your own ChatGPT login session token.  
Not affiliated with OpenAI. Follow OpenAI ToS and local laws.

## Live deployment

Implemented product: **https://voice.peekcart.com/**
