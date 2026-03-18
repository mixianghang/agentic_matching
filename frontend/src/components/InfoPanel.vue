<template>
  <div class="info-panel">

    <!-- Empty state -->
    <div v-if="!app.currentTask" class="empty-state">
      <div class="empty-icon">📋</div>
      <p>选择一个任务查看详情</p>
    </div>

    <template v-else>
      <!-- Task basic info -->
      <section class="section task-info">
        <h4 class="section-title">任务信息</h4>
        <van-cell-group inset>
          <van-cell title="类型" :value="typeLabel(app.currentTask.task_type)" />
          <van-cell title="状态" :value="statusLabel(app.currentTask.status)" />
          <van-cell v-if="app.currentTask.description" title="描述" :label="app.currentTask.description" />
        </van-cell-group>
      </section>

      <!-- Structured demand values -->
      <section
        v-if="structuredValues && Object.keys(structuredValues).length"
        class="section"
      >
        <h4 class="section-title">需求详情</h4>
        <van-cell-group inset>
          <van-cell
            v-for="(val, key) in structuredValues"
            :key="key"
            :title="fieldLabel(key)"
            :value="String(val)"
          />
        </van-cell-group>
      </section>

      <!-- Demand progress -->
      <section v-if="app.demandProgress?.has_session" class="section">
        <h4 class="section-title">需求进度</h4>
        <van-cell-group inset>
          <van-cell title="状态" :value="progressStateLabel" />
          <van-cell
            v-if="app.demandProgress.demand_type"
            title="类型"
            :value="app.demandProgress.demand_type"
          />
          <van-cell
            v-if="app.demandProgress.role"
            title="角色"
            :value="app.demandProgress.role"
          />
          <van-cell
            v-if="app.demandProgress.custom_requirements"
            title="附加要求"
            :label="app.demandProgress.custom_requirements"
          />
        </van-cell-group>

        <!-- Collected field values -->
        <template v-if="filledValues && Object.keys(filledValues).length">
          <p class="sub-label">已填信息</p>
          <van-cell-group inset>
            <van-cell
              v-for="(val, key) in filledValues"
              :key="key"
              :title="fieldLabel(key)"
              :value="String(val)"
            />
          </van-cell-group>
        </template>

        <!-- Pending fields -->
        <template v-if="pendingFields.length">
          <p class="sub-label">待填信息</p>
          <van-cell-group inset>
            <van-cell
              v-for="f in pendingFields"
              :key="f"
              :title="f"
              value="—"
            />
          </van-cell-group>
        </template>
      </section>

      <!-- Match results -->
      <section v-if="showMatches" class="section">
        <div class="section-header">
          <h4 class="section-title">匹配结果</h4>
          <van-button size="mini" type="primary" plain @click="refreshMatches">刷新匹配</van-button>
        </div>

        <div v-if="!app.matchResults?.length" class="no-matches">
          <p>暂无匹配结果</p>
        </div>

        <div v-else class="match-list">
          <div
            v-for="m in app.matchResults"
            :key="m.id"
            class="match-card"
          >
            <div class="match-header">
              <van-tag :color="typeColor(m.task_type)">{{ typeLabel(m.task_type) }}</van-tag>
              <span class="match-score" v-if="m.score != null">{{ Math.round(m.score * 100) }}%</span>
            </div>
            <p class="match-desc">{{ m.description || '（暂无描述）' }}</p>
          </div>
        </div>
      </section>

      <!-- Actions -->
      <section class="section actions">
        <van-button
          block
          type="danger"
          plain
          @click="handleDelete"
          style="margin-top: 8px"
        >
          删除此需求
        </van-button>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useAppStore } from '@/stores/app'
import { tasksApi } from '@/api/tasks'

const app = useAppStore()

// --- Computed helpers ---

const structuredValues = computed(() =>
  app.currentTask?.metadata?.structured_demand?.values ?? null
)

const filledValues = computed(() =>
  app.demandProgress?.values ?? null
)

const pendingFields = computed(() =>
  app.demandProgress?.pending_fields ?? []
)

const showMatches = computed(() =>
  !!(app.currentTask?.metadata?.demand_completed || app.demandProgress?.is_complete)
)

const progressStateLabel = computed(() => {
  const stateMap: Record<string, string> = {
    initial: '初始化',
    type_detection: '类型识别',
    field_collection: '信息收集',
    confirmation: '待确认',
    completed: '已完成',
  }
  const s = app.demandProgress?.state ?? ''
  return stateMap[s] ?? s
})

// --- Formatters ---

function typeLabel(type: string | undefined) {
  const m: Record<string, string> = { rental: '租房', dating: '相亲交友', gaming: '游戏组队', new: '新建', pending: '待定' }
  return m[type ?? 'new'] ?? type ?? '—'
}

function statusLabel(status: string | undefined) {
  const m: Record<string, string> = { active: '进行中', completed: '已完成', pending: '等待中', cancelled: '已取消' }
  return m[status ?? ''] ?? status ?? '—'
}

function typeColor(type: string | undefined) {
  const m: Record<string, string> = { rental: '#3b82f6', dating: '#ec4899', gaming: '#8b5cf6', new: '#9ca3af' }
  return m[type ?? ''] ?? '#9ca3af'
}

function fieldLabel(key: string) {
  const labelMap: Record<string, string> = {
    location: '地点', budget: '预算', area: '面积', room_type: '户型',
    gender: '性别', age_range: '年龄段', district: '区域',
    game_name: '游戏名称', rank: '段位', role: '角色',
    move_in_date: '入住时间', duration: '时长',
  }
  return labelMap[key] ?? key
}

async function refreshMatches() {
  if (!app.currentTask) return
  const matches = await tasksApi.getMatches(app.currentTask.id)
  app.matchResults = matches
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
</script>

<style scoped>
.info-panel {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 8px 0 24px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px;
  color: #bbb;
}

.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-state p { font-size: 14px; }

.section { margin: 12px 0; }

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  padding: 0 16px;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  margin-bottom: 6px;
}

.section-header .section-title { margin-bottom: 0; padding: 0; }

.sub-label {
  font-size: 11px;
  color: #aaa;
  padding: 6px 20px 2px;
}

.no-matches {
  padding: 16px 20px;
  font-size: 13px;
  color: #aaa;
}

.match-list { padding: 0 12px; display: flex; flex-direction: column; gap: 8px; }

.match-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 14px;
  background: #fff;
}

.match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.match-score {
  font-size: 13px;
  font-weight: 600;
  color: #667eea;
}

.match-desc {
  font-size: 13px;
  color: #555;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.actions { padding: 0 16px; }
</style>
