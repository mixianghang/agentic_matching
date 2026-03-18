<template>
  <div class="message" :class="type">
    <div class="bubble" v-html="formattedContent" />
    <div class="time">{{ formattedTime }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  content: string
  type: 'user' | 'agent' | 'system'
  timestamp: string
}>()

// Safely render agent messages: escape HTML, then convert markdown-bold and newlines
const formattedContent = computed(() => {
  const escaped = props.content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // *text* or **text** → bold
  const bolded = escaped.replace(/\*\*?([^*\n]+)\*\*?/g, '<strong>$1</strong>')
  // Newlines → <br>
  return bolded.replace(/\n/g, '<br>')
})

const formattedTime = computed(() => {
  const d = new Date(props.timestamp)
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
})
</script>

<style scoped>
.message {
  display: flex;
  flex-direction: column;
  max-width: 78%;
  margin-bottom: 16px;
}

.message.user { align-items: flex-end; margin-left: auto; }
.message.agent { align-items: flex-start; }
.message.system { align-items: center; margin: 0 auto; max-width: 90%; }

.bubble {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user .bubble {
  background: var(--color-primary-gradient);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.agent .bubble {
  background: #f3f4f6;
  color: #333;
  border-bottom-left-radius: 4px;
}

.system .bubble {
  background: #f0f4ff;
  color: #667eea;
  font-size: 13px;
  border-radius: 8px;
  text-align: center;
}

.time {
  font-size: 11px;
  color: #bbb;
  margin-top: 4px;
}

.user .time { text-align: right; }
</style>
