<template>
  <div class="chat-area">

    <!-- Welcome screen when no task -->
    <div v-if="!app.currentTask" class="welcome">
      <div class="welcome-icon">💬</div>
      <h2>开始你的对话</h2>
      <p>从左侧选择一个需求，或点击"新建需求"</p>
    </div>

    <!-- Chat view when task is selected -->
    <template v-else>
      <!-- Desktop header -->
      <div class="chat-header desktop-only">
        <div class="header-left">
          <h3>{{ taskTitle }}</h3>
          <p>创建于 {{ formatDate(app.currentTask.created_at) }}</p>
        </div>
        <van-button
          size="small"
          type="danger"
          plain
          icon="delete-o"
          @click="handleDelete"
        />
      </div>

      <!-- Messages -->
      <div class="messages" ref="messagesEl">
        <MessageBubble
          v-for="msg in app.currentTask.messages"
          :key="msg.id"
          :content="msg.content"
          :type="msgType(msg)"
          :timestamp="msg.timestamp"
        />
        <!-- Agent typing indicator -->
        <div v-if="app.sending" class="typing-indicator">
          <span /><span /><span />
        </div>
      </div>

      <!-- Input area -->
      <div class="input-area">
        <van-field
          v-model="inputText"
          type="textarea"
          :autosize="{ minHeight: 36, maxHeight: 100 }"
          :border="false"
          placeholder="输入消息…"
          class="input-field"
          @keydown.enter.exact.prevent="handleSend"
        />
        <!-- Microphone button — icons from Heroicons (MIT License, https://heroicons.com) -->
        <button
          :class="['mic-icon-btn', { 'mic-icon-btn--recording': micState === 'recording', 'mic-icon-btn--processing': micState === 'processing' }]"
          :disabled="app.sending || micState === 'processing'"
          type="button"
          :aria-label="micState === 'recording' ? '停止录音' : '语音输入'"
          @click="handleMicClick"
        >
          <!-- Heroicons: microphone (MIT) -->
          <svg v-if="micState === 'idle'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M8.25 4.5a3.75 3.75 0 1 1 7.5 0v8.25a3.75 3.75 0 1 1-7.5 0V4.5Z" />
            <path d="M6 10.5a.75.75 0 0 1 .75.75v1.5a5.25 5.25 0 1 0 10.5 0v-1.5a.75.75 0 0 1 1.5 0v1.5a6.751 6.751 0 0 1-6 6.709v2.291h3a.75.75 0 0 1 0 1.5h-7.5a.75.75 0 0 1 0-1.5h3v-2.291a6.751 6.751 0 0 1-6-6.709v-1.5A.75.75 0 0 1 6 10.5Z" />
          </svg>
          <!-- Heroicons: stop-circle (MIT) -->
          <svg v-else-if="micState === 'recording'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm6-2.438c0-.724.588-1.312 1.313-1.312h4.874c.725 0 1.313.588 1.313 1.313v4.874c0 .725-.588 1.313-1.313 1.313H9.564A1.312 1.312 0 0 1 8.25 14.436V9.562Z" clip-rule="evenodd" />
          </svg>
          <!-- Spinner for processing state -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" width="20" height="20" class="mic-spin">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-dasharray="42 14" />
          </svg>
        </button>
        <van-button
          type="primary"
          :loading="app.sending"
          :disabled="!inputText.trim()"
          size="normal"
          round
          @click="handleSend"
        >
          发送
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useAppStore } from '@/stores/app'
import MessageBubble from './MessageBubble.vue'
import type { Message } from '@/api/tasks'
import { tasksApi } from '@/api/tasks'

const app = useAppStore()

const inputText = ref('')
const messagesEl = ref<HTMLElement>()

// --- voice recording state ---
type MicState = 'idle' | 'recording' | 'processing'
const micState = ref<MicState>('idle')
let mediaRecorder: MediaRecorder | null = null
let audioChunks: BlobPart[] = []
let maxRecordingTimer: ReturnType<typeof setTimeout> | null = null
const MAX_RECORDING_MS = 60_000

const taskTitleMap: Record<string, string> = {
  rental: '租房需求', dating: '相亲交友', gaming: '游戏组队', new: '需求对话中', pending: '需求对话中',
}

const taskTitle = computed(() => {
  const t = app.currentTask?.task_type ?? 'new'
  return taskTitleMap[t] ?? '需求对话'
})

function msgType(msg: Message): 'user' | 'agent' | 'system' {
  if (msg.message_type === 'user') return 'user'
  if (msg.message_type === 'system') return 'system'
  return 'agent'
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// Auto-scroll to bottom when messages change
watch(
  () => app.currentTask?.messages?.length,
  async () => {
    await nextTick()
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  },
)

async function handleSend() {
  const content = inputText.value.trim()
  if (!content || app.sending) return
  inputText.value = ''
  await app.sendMessage(content)
}

async function handleDelete() {
  try {
    await showConfirmDialog({ title: '删除需求', message: '确定删除此需求？操作不可撤销。' })
    await app.deleteCurrentTask()
    showToast('已删除')
  } catch {
    // cancelled
  }
}

async function handleMicClick() {
  if (micState.value === 'recording') {
    // Stop recording
    mediaRecorder?.stop()
    return
  }

  if (micState.value !== 'idle') return

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []
    const preferredMimeTypes = [
      'audio/ogg;codecs=opus',
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
    ]
    const mimeType = preferredMimeTypes.find((t) => MediaRecorder.isTypeSupported(t)) || ''
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }

    mediaRecorder.onstop = async () => {
      // Stop all tracks to release mic
      stream.getTracks().forEach((t) => t.stop())
      if (maxRecordingTimer) { clearTimeout(maxRecordingTimer); maxRecordingTimer = null }

      micState.value = 'processing'
      const blob = new Blob(audioChunks, { type: mimeType || 'application/octet-stream' })
      audioChunks = []

      try {
        const result = await tasksApi.transcribeAudio(blob)
        if (result.text) {
          inputText.value = result.text
          await handleSend()
        } else {
          showToast('未识别到语音，请重试')
        }
      } catch {
        showToast('语音识别失败，请重试')
      } finally {
        micState.value = 'idle'
      }
    }

    mediaRecorder.start()
    micState.value = 'recording'

    // Auto-stop after MAX_RECORDING_MS
    maxRecordingTimer = setTimeout(() => {
      if (micState.value === 'recording') {
        showToast('录音已达最长时长')
        mediaRecorder?.stop()
      }
    }, MAX_RECORDING_MS)
  } catch {
    showToast('无法访问麦克风，请检查权限')
    micState.value = 'idle'
  }
}
</script>

<style scoped>
.chat-area {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px;
  color: #888;
}

.welcome-icon { font-size: 64px; margin-bottom: 20px; }
.welcome h2 { font-size: 20px; color: #555; margin-bottom: 8px; }
.welcome p { font-size: 14px; }

/* Desktop header */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafbfc;
}

.chat-header h3 { font-size: 16px; color: #333; margin-bottom: 2px; }
.chat-header p { font-size: 12px; color: #999; }

/* Messages */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

/* Input */
.input-area {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
  background: #fafbfc;
}

.input-field {
  flex: 1;
  background: #f0f2f5;
  border-radius: 12px;
  padding: 0 4px;
}

/* Agent typing dots */
.typing-indicator {
  display: flex;
  gap: 5px;
  padding: 12px 16px;
  align-self: flex-start;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  animation: bounce 1.2s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1.2); opacity: 1; }
}

/* Mobile: hide desktop header */
@media (max-width: 767px) {
  .desktop-only { display: none; }
  .messages { padding: 16px; }
}

/* Microphone icon button */
.mic-icon-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #f0f2f5;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, box-shadow 0.2s;
  outline: none;
}
.mic-icon-btn:hover:not(:disabled) {
  background: #e5e7eb;
  color: #374151;
}
.mic-icon-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
.mic-icon-btn--recording {
  background: #fee2e2;
  color: #ef4444;
  animation: mic-pulse 1.2s ease-in-out infinite;
}
.mic-icon-btn--processing {
  background: #f0f2f5;
  color: #9ca3af;
}
.mic-spin {
  animation: spin 1s linear infinite;
}

@keyframes mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.35); }
  50%       { box-shadow: 0 0 0 7px rgba(239, 68, 68, 0); }
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
