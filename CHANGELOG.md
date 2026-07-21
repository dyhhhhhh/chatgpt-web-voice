# Changelog

## v0.1.0 - 2026-07-21

### Added
- Standalone FastAPI voice gateway (no chat2/yukkcat admin stack)
- `POST /api/voice/session` WebRTC SDP proxy to ChatGPT `/realtime/wm`
- `POST /api/voice/upload-image` for in-call image `file_id`
- `POST /api/voice/session/release` session/token unbind
- Browser client `static/voice.html`
  - realtime call
  - in-call text via `relay_message`
  - in-call image via sediment pointer
  - captions (`chat_message_delta`)
  - auto barge-in interrupt (`stop_speaking`)
- Docker + docker-compose one-command start
- Live demo: https://voice.peekcart.com/
