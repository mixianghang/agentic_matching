import { defineStore } from 'pinia'
import { ref } from 'vue'
import { tasksApi, type Task, type Message, type DemandProgress } from '@/api/tasks'
import { useAuthStore } from './auth'

export const useAppStore = defineStore('app', () => {
  const tasks = ref<Task[]>([])
  const currentTask = ref<Task | null>(null)
  const demandProgress = ref<DemandProgress | null>(null)
  const matchResults = ref<Task[]>([])
  const sending = ref(false)
  const taskLoading = ref(false)

  async function loadTasks() {
    const auth = useAuthStore()
    const all = await tasksApi.list()
    // Backend already filters by user, but guard just in case
    tasks.value = all.filter((t) => t.user_id === auth.user?.id)
  }

  async function createTask() {
    const task = await tasksApi.create()
    tasks.value.unshift(task)
    await selectTask(task.id)
    return task
  }

  async function selectTask(id: string) {
    taskLoading.value = true
    try {
      const task = await tasksApi.get(id)
      currentTask.value = task
      _syncTaskInList(task)
      await _refreshSidePanel()
    } finally {
      taskLoading.value = false
    }
  }

  async function sendMessage(content: string) {
    if (!currentTask.value || !content.trim() || sending.value) return
    sending.value = true

    // Optimistic: add user message immediately
    const userMsg: Message = {
      id: `tmp-${Date.now()}`,
      sender_id: 'user',
      content,
      message_type: 'user',
      timestamp: new Date().toISOString(),
    }
    if (!currentTask.value.messages) currentTask.value.messages = []
    currentTask.value.messages.push(userMsg)

    try {
      const taskId = currentTask.value.id
      const res = await tasksApi.sendMessage(taskId, content)
      currentTask.value?.messages?.push(res.message)
      // Refresh task metadata (type, status, structured demand)
      await _refreshCurrentTaskMeta()
    } finally {
      sending.value = false
    }
  }

  async function deleteCurrentTask() {
    if (!currentTask.value) return
    const id = currentTask.value.id
    await tasksApi.remove(id)
    tasks.value = tasks.value.filter((t) => t.id !== id)
    currentTask.value = null
    demandProgress.value = null
    matchResults.value = []
  }

  // Internal helpers

  async function _refreshCurrentTaskMeta() {
    if (!currentTask.value) return
    const updated = await tasksApi.get(currentTask.value.id)
    // Merge: keep local messages, update everything else
    const localMessages = currentTask.value.messages
    Object.assign(currentTask.value, updated)
    if (!currentTask.value.messages?.length && localMessages?.length) {
      currentTask.value.messages = localMessages
    }
    _syncTaskInList({ ...updated, messages: currentTask.value.messages })
    await _refreshSidePanel()
  }

  async function _refreshSidePanel() {
    if (!currentTask.value) return
    const [progress] = await Promise.all([
      tasksApi.getDemandProgress(currentTask.value.id),
      _loadMatches(),
    ])
    demandProgress.value = progress
  }

  async function _loadMatches() {
    if (!currentTask.value?.metadata?.demand_completed) {
      matchResults.value = []
      return
    }
    const res = await tasksApi.getMatches(currentTask.value.id)
    matchResults.value = res.matches
  }

  function _syncTaskInList(task: Task) {
    const idx = tasks.value.findIndex((t) => t.id === task.id)
    if (idx >= 0) tasks.value[idx] = task
  }

  return {
    tasks,
    currentTask,
    demandProgress,
    matchResults,
    sending,
    taskLoading,
    loadTasks,
    createTask,
    selectTask,
    sendMessage,
    deleteCurrentTask,
  }
})
