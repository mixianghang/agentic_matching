<template>
  <!--
    Desktop (≥768px): all 3 columns always visible side by side.
    Mobile (<768px):   one panel visible at a time, controlled by mobilePanel.
  -->
  <div class="home" :class="mobilePanelClass">

    <!-- ══ LEFT: Task List ══ -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div>
          <h2>智能需求匹配</h2>
          <p>欢迎，{{ auth.user?.username }}</p>
        </div>
        <van-button size="small" plain @click="handleLogout">退出</van-button>
      </div>

      <TaskList @select="onSelectTask" @create="onCreateTask" />
    </aside>

    <!-- ══ CENTER: Chat ══ -->
    <main class="chat-pane">
      <!-- Mobile nav bar shown only when a task is selected -->
      <van-nav-bar
        v-if="app.currentTask"
        class="mobile-only-nav"
        :title="currentTaskTitle"
        left-arrow
        @click-left="mobilePanel = 'list'"
      >
        <template #right>
          <span class="nav-detail-btn" @click="mobilePanel = 'info'">详情</span>
        </template>
      </van-nav-bar>

      <ChatArea />
    </main>

    <!-- ══ RIGHT: Info Panel ══ -->
    <aside class="info-pane">
      <van-nav-bar
        class="mobile-only-nav"
        title="需求详情"
        left-arrow
        @click-left="mobilePanel = 'chat'"
      />
      <InfoPanel />
    </aside>

    <!-- Mobile bottom tabs (only when task is open) -->
    <van-tabbar
      v-if="app.currentTask"
      class="mobile-only-tabbar"
      v-model="mobilePanel"
      active-color="#667eea"
    >
      <van-tabbar-item name="list" icon="list-switch">我的需求</van-tabbar-item>
      <van-tabbar-item name="chat" icon="chat-o">对话</van-tabbar-item>
      <van-tabbar-item name="info" icon="description">详情</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import TaskList from '@/components/TaskList.vue'
import ChatArea from '@/components/ChatArea.vue'
import InfoPanel from '@/components/InfoPanel.vue'

const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

// Mobile panel control
const mobilePanel = ref<'list' | 'chat' | 'info'>('list')

// Navigate to chat automatically when a task is selected
watch(() => app.currentTask, (task) => {
  if (task) mobilePanel.value = 'chat'
})

const mobilePanelClass = computed(() => `panel-${mobilePanel.value}`)

const currentTaskTitle = computed(() => {
  if (!app.currentTask) return ''
  const typeNames: Record<string, string> = {
    rental: '租房需求', dating: '相亲交友', gaming: '游戏组队', new: '需求对话中',
  }
  return typeNames[app.currentTask.task_type] || '需求对话'
})

async function onSelectTask(id: string) {
  await app.selectTask(id)
}

async function onCreateTask() {
  await app.createTask()
}

async function handleLogout() {
  try {
    await showConfirmDialog({ title: '退出登录', message: '确定要退出吗？' })
    auth.logout()
    router.replace('/login')
  } catch {
    // cancelled
  }
}

// Load tasks on mount
app.loadTasks()
</script>

<style scoped>
.home {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ── Column sizing ── */
.sidebar {
  width: 300px;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e7eb;
  background: #f7f8fa;
}

.chat-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.info-pane {
  width: 300px;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e5e7eb;
  background: #f7f8fa;
  overflow-y: auto;
}

/* ── Sidebar header ── */
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 16px;
  background: var(--color-primary-gradient);
  color: #fff;
}

.sidebar-header h2 {
  font-size: 16px;
  margin-bottom: 2px;
}

.sidebar-header p {
  font-size: 12px;
  opacity: 0.85;
}

/* ── Mobile: hide all panels by default, show active one ── */
.mobile-only-nav { display: none; }
.mobile-only-tabbar { display: none; }

@media (max-width: 767px) {
  .home {
    flex-direction: column;
    position: relative;
  }

  .sidebar, .chat-pane, .info-pane {
    position: absolute;
    inset: 0;
    width: 100%;
    min-width: unset;
    display: none;
    border: none;
  }

  /* Show active panel */
  .panel-list .sidebar { display: flex; }
  .panel-chat .chat-pane { display: flex; }
  .panel-info .info-pane { display: flex; }

  .mobile-only-nav { display: flex; }
  .mobile-only-tabbar { display: flex !important; }
}

.nav-detail-btn {
  font-size: 14px;
  color: #667eea;
  cursor: pointer;
}
</style>
