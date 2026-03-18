<template>
  <div class="login-page">
    <div class="login-header">
      <div class="app-logo">🤖</div>
      <h1>智能需求匹配</h1>
      <p>让智能体帮你完成需求匹配</p>
    </div>

    <div class="tab-switcher">
      <button :class="['tab-btn', { active: mode === 'login' }]" @click="mode = 'login'">登录</button>
      <button :class="['tab-btn', { active: mode === 'register' }]" @click="mode = 'register'">注册</button>
    </div>

    <van-form @submit="handleSubmit" class="login-form">
      <van-cell-group inset>
        <van-field
          v-model="username"
          name="username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        />
        <van-field
          v-model="password"
          type="password"
          name="password"
          label="密码"
          placeholder="请输入密码（至少6位）"
          :rules="[{ required: true, message: '请输入密码' }, { validator: validatePassword }]"
        />
        <van-field
          v-if="mode === 'register'"
          v-model="confirmPassword"
          type="password"
          name="confirmPassword"
          label="确认密码"
          placeholder="再次输入密码"
          :rules="[{ validator: validateConfirm }]"
        />
        <van-field
          v-if="mode === 'register'"
          v-model="email"
          name="email"
          label="邮箱"
          placeholder="可选"
        />
      </van-cell-group>

      <div class="form-actions">
        <van-button
          block
          type="primary"
          native-type="submit"
          :loading="loading"
          size="large"
          round
        >
          {{ mode === 'login' ? '登录' : '注册' }}
        </van-button>
      </div>
    </van-form>

    <div class="third-party">
      <div class="divider"><span>或使用第三方登录</span></div>
      <div class="third-party-btns">
        <van-button plain round @click="ssoLogin('wechat')">💬 微信</van-button>
        <van-button plain round @click="ssoLogin('alipay')">💰 支付宝</van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const email = ref('')
const loading = ref(false)

function validatePassword(val: string) {
  if (val.length < 6) return '密码至少6位'
  return true
}

function validateConfirm(val: string) {
  if (val !== password.value) return '两次密码不一致'
  return true
}

async function handleSubmit() {
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value, password.value)
    } else {
      await auth.register(username.value, password.value, email.value || undefined)
    }
    const redirect = (route.query.redirect as string) || '/home'
    router.replace(redirect)
  } catch (e: unknown) {
    const msg = (e as { detail?: string })?.detail || (e instanceof Error ? e.message : '操作失败')
    showToast(msg)
  } finally {
    loading.value = false
  }
}

async function ssoLogin(provider: string) {
  try {
    const res = await fetch(`/api/auth/sso/${provider}/url`)
    const data = await res.json()
    if (res.ok && data.auth_url) {
      localStorage.setItem('sso_provider', provider)
      window.location.href = data.auth_url
    } else {
      showToast(data.detail || '获取登录链接失败')
    }
  } catch {
    showToast('登录失败，请稍后重试')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #ede9fe 0%, #fff 40%);
  padding-bottom: 40px;
}

.login-header {
  text-align: center;
  padding: 60px 20px 32px;
}

.app-logo {
  font-size: 64px;
  margin-bottom: 12px;
}

.login-header h1 {
  font-size: 24px;
  font-weight: 700;
  background: var(--color-primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.login-header p {
  color: #888;
  margin-top: 6px;
  font-size: 14px;
}

.tab-switcher {
  display: flex;
  gap: 12px;
  padding: 0 16px 16px;
  justify-content: center;
}

.tab-btn {
  flex: 1;
  max-width: 140px;
  padding: 10px;
  border: 2px solid #e0d9f7;
  border-radius: 24px;
  background: transparent;
  font-size: 15px;
  font-weight: 600;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: var(--color-primary-gradient);
  color: #fff;
  border-color: transparent;
}

.login-form {
  padding: 0 0 16px;
}

.form-actions {
  padding: 20px 16px 0;
}

.third-party {
  padding: 24px 16px 0;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #bbb;
  font-size: 13px;
  margin-bottom: 16px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e5e7eb;
}

.third-party-btns {
  display: flex;
  gap: 12px;
}

.third-party-btns .van-button {
  flex: 1;
}
</style>
