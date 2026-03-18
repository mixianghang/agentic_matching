import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'
import { Locale } from 'vant'
import zhCN from 'vant/es/locale/lang/zh-CN'
import 'vant/lib/index.css'

import App from './App.vue'
import router from './router'

Locale.use('zh-CN', zhCN)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(Vant)
app.mount('#app')
