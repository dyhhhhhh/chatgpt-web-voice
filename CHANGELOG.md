# Changelog

## v0.1.1 - 2026-07-23

### Added
- In-call account failover: when the active web token dies or the WebRTC call drops, the browser automatically releases the bound session and reconnects with another account from the pool (up to 3 attempts).
- DataChannel signals handled for failover: `usage_update` hang_up / exceed limit / near-zero `audio_s`, and hangup tool updates.
- Upload path returns **401** and marks the token invalid when ChatGPT rejects the session token mid-call.

### Changed
- `static/voice.html` reconnect UX: toast + status text during account switch; user hang-up cancels pending failover.
- Session create already rotated on 401; mid-call path now reuses that server rotation after a clean SDP re-offer.

## v0.1.0 - 2026-07-21
 - 2026-07-21

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
