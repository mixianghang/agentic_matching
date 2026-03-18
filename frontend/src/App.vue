<template>
  <router-view />
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', 'Segoe UI', sans-serif;
  background: #f5f5f5;
  color: #333;
}

#app {
  height: 100%;
  background: #fff;
}

:root {
  --color-primary: #667eea;
  --color-primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --van-primary-color: #667eea;
  --van-button-primary-background: #667eea;
  --van-button-primary-border-color: #667eea;
}
</style>
