import api from './index'

export interface Message {
  id: string
  sender_id: string
  receiver_id?: string
  content: string
  message_type: string   // 'user' | 'agent' | 'system'
  timestamp: string
}

export interface Task {
  id: string
  user_id: string
  agent_id: string
  task_type: string      // 'new' | 'rental' | 'dating' | 'gaming'
  description: string
  status: string         // 'pending' | 'active' | 'matching' | 'matched' | 'completed'
  requirements: Record<string, unknown>
  metadata: {
    demand_session_id?: string
    structured_demand?: { values?: Record<string, unknown> }
    demand_completed?: boolean
  }
  created_at: string
  updated_at: string
  messages?: Message[]
  score?: number
}

export interface DemandProgress {
  has_session: boolean
  state?: string
  demand_type?: string
  role?: string
  filled_fields?: string[]
  pending_fields?: string[]
  is_complete?: boolean
  values?: Record<string, unknown>
  custom_requirements?: string[]
}

export const tasksApi = {
  list() {
    return api.get<never, Task[]>('/tasks/')
  },
  get(id: string) {
    return api.get<never, Task>(`/tasks/${id}`)
  },
  create() {
    return api.post<never, Task>('/tasks/', {
      task_type: 'new',
      description: '新建需求对话中...',
      requirements: {},
    })
  },
  update(id: string, data: Partial<Task>) {
    return api.put<never, Task>(`/tasks/${id}`, data)
  },
  remove(id: string) {
    return api.delete(`/tasks/${id}`)
  },
  sendMessage(task_id: string, user_message: string) {
    return api.post<never, { message: Message }>('/messages/', { task_id, user_message })
  },
  getMatches(task_id: string) {
    return api.get<never, { matches: Task[] }>(`/tasks/${task_id}/matches/`)
  },
  getDemandProgress(task_id: string) {
    return api.get<never, DemandProgress>(`/tasks/${task_id}/demand_progress`)
  },
  transcribeAudio(blob: Blob) {
    const form = new FormData()
    const mime = blob.type || 'application/octet-stream'
    const extMap: Record<string, string> = {
      'audio/webm': 'webm',
      'audio/webm;codecs=opus': 'webm',
      'audio/ogg': 'ogg',
      'audio/ogg;codecs=opus': 'ogg',
      'audio/mp4': 'mp4',
      'audio/mpeg': 'mp3',
      'audio/wav': 'wav',
      'audio/x-wav': 'wav',
    }
    const ext = extMap[mime] || 'bin'
    form.append('file', blob, `audio.${ext}`)
    // Do NOT set Content-Type manually — axios must auto-set it with the multipart boundary
    return api.post<never, { text: string }>('/asr/transcribe', form)
  },
}
