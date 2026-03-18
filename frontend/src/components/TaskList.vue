<template>
  <div class="task-list-wrapper">
    <div class="new-task-bar">
      <van-button
        block
        type="primary"
        size="small"
        plain
        icon="plus"
        :loading="creating"
        @click="handleCreate"
      >
        新建需求
      </van-button>
    </div>

    <div v-if="app.tasks.length === 0" class="empty-state">
      <p>点击上方按钮创建你的第一个需求</p>
    </div>

    <div v-else class="task-items">
      <div
        v-for="task in app.tasks"
        :key="task.id"
        :class="['task-card', { active: app.currentTask?.id === task.id }]"
        @click="$emit('select', task.id)"
      >
        <div class="task-card-row">
          <van-tag :color="typeColor(task.task_type)" text-color="#fff">
            {{ typeName(task.task_type) }}
          </van-tag>
          <span class="task-status">{{ statusName(task.status) }}</span>
        </div>
        <div class="task-preview">{{ previewText(task.description) }}</div>
        <div class="task-date">{{ formatDate(task.created_at) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/app'
import type { Task } from '@/api/tasks'

const emit = defineEmits<{
  select: [id: string]
  create: []
}>()

const app = useAppStore()
const creating = ref(false)

async function handleCreate() {
  creating.value = true
  try {
    emit('create')
  } finally {
    creating.value = false
  }
}

function typeName(type: string) {
  const map: Record<string, string> = { rental: '租房', dating: '相亲', gaming: '游戏', new: '新建', pending: '待定' }
  return map[type] ?? '需求'
}

function typeColor(type: string) {
  const map: Record<string, string> = { rental: '#3b82f6', dating: '#ec4899', gaming: '#8b5cf6', new: '#9ca3af', pending: '#f59e0b' }
  return map[type] ?? '#667eea'
}

function statusName(status: string) {
  const map: Record<string, string> = {
    pending: '待处理', active: '进行中', matching: '匹配中',
    matched: '已匹配', completed: '已完成', cancelled: '已取消',
  }
  return map[status] ?? status
}

function previewText(desc: string) {
  return desc.length > 48 ? desc.slice(0, 48) + '…' : desc
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.task-list-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.new-task-bar {
  padding: 12px 14px;
  border-bottom: 1px solid #e5e7eb;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: #aaa;
  font-size: 14px;
}

.task-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
}

.task-card {
  padding: 12px 14px;
  margin-bottom: 8px;
  background: #fff;
  border-radius: 10px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.18s;
}

.task-card:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.task-card.active {
  border-color: #667eea;
  background: #f0f4ff;
}

.task-card-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.task-status {
  font-size: 12px;
  color: #888;
}

.task-preview {
  font-size: 13px;
  color: #555;
  line-height: 1.4;
  margin-bottom: 6px;
}

.task-date {
  font-size: 11px;
  color: #bbb;
}
</style>
