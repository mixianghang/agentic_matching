# Voice Input Design v1.0

## Overview

Add voice input to the chat interface. The user presses a microphone button, speaks, and the recorded audio is sent to a server-side ASR (Automatic Speech Recognition) model. The transcribed text is populated into the chat input box and sent as a regular user message.

---

## Architecture

```
Browser (MediaRecorder API)
    │  audio blob (WebM/OGG)
    ▼
POST /api/asr/transcribe   ← our FastAPI backend (proxies & authenticates)
    │  multipart/form-data: file=<audio>, model=<ASR_MODEL>
    ▼
ASR Server  (OpenAI-compatible, e.g. localhost:61234)
POST /v1/audio/transcriptions
    │  { "text": "recognized text..." }
    ▼
Backend returns { "text": "..." } to browser
    │
    ▼
Frontend populates inputText + auto-sends message
```

The backend acts as a secure proxy so the ASR API key is never exposed to the browser.

---

## Components

### 1. Configuration (Backend)

New settings in `backend/config.py` and `.env`:

| Variable       | Default                        | Purpose                         |
|----------------|--------------------------------|---------------------------------|
| `ASR_BASE_URL` | `http://localhost:61234/v1`    | Base URL of the ASR server      |
| `ASR_API_KEY`  | `""`                           | API key for the ASR server      |
| `ASR_MODEL`    | `whisper-1`                    | ASR model name to request       |

### 2. Backend Endpoint

`POST /api/asr/transcribe`

- **Auth:** requires valid JWT (same as all other API calls)
- **Input:** `multipart/form-data` with field `file` (audio blob, any browser-supported format: WebM, OGG, WAV)
- **Processing:** forwards the file to `{ASR_BASE_URL}/audio/transcriptions` with the configured model and API key (via `httpx` – already in requirements)
- **Output:** `{ "text": "<transcribed text>" }`
- **Error handling:** returns 503 if ASR server unreachable, 500 for other failures

### 3. Frontend API (`frontend/src/api/tasks.ts`)

New function added to `tasksApi`:

```ts
transcribeAudio(blob: Blob): Promise<{ text: string }>
```

Sends the audio blob as `FormData` to `/api/asr/transcribe`.

### 4. Frontend UI (`frontend/src/components/ChatArea.vue`)

#### States
- **idle** – microphone button shown, greyed out / normal
- **recording** – button turns red, pulsing animation, recording in progress
- **processing** – button shows spinner while waiting for ASR response

#### Interaction flow
1. User taps/clicks the microphone button → starts recording via `MediaRecorder`
2. User taps/clicks again (or recording auto-stops after max 60 s) → stops recording
3. Frontend sends audio blob to backend ASR endpoint
4. On success: transcribed text is placed in `inputText`; `handleSend()` is called automatically
5. On error: `showToast` displays the error

#### UX details
- Button is disabled while a message is being sent (`app.sending`)
- Max recording duration: 60 seconds (auto-stops with a warning toast)
- Uses `MediaRecorder` with `audio/webm` MIME type (falls back to browser default)
- Input area layout: `[text field] [mic button] [send button]`

---

## Security Notes

- ASR API key is stored only in `.env` on the server, never sent to the client.
- The transcription endpoint is behind JWT authentication to prevent abuse.
- Uploaded audio is streamed directly to the ASR server and never persisted to disk.

---

## Future Considerations

- Support multiple ASR providers (local Whisper, cloud APIs) via the same factory pattern used for LLMs and SSO.
- Add language hint parameter (default: `zh` for Chinese, configurable per user).
- Real-time streaming transcription via WebSocket for lower latency.
- Client-side voice activity detection (VAD) to auto-stop recording on silence.
