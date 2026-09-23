<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="logo">
        <span>🎬</span>
        <span class="logo-text">直播带货 AI Agent</span>
      </div>
      <el-menu :default-active="$route.path" mode="horizontal" router class="nav-menu">
        <el-menu-item index="/"><span>📊 数据看板</span></el-menu-item>
        <el-menu-item index="/live"><span>🔴 直播间</span></el-menu-item>
      </el-menu>
      <el-tag :type="isConnected ? 'success' : 'danger'" effect="dark">
        {{ isConnected ? '🟢 已连接' : '🔴 未连接' }}
      </el-tag>
    </el-header>
    <el-main><router-view /></el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useMainStore } from '@/stores'
const store = useMainStore()
const isConnected = computed(() => store.isConnected)
onMounted(() => store.connect('default'))
</script>

<style>
html, body, #app { height: 100%; margin: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.app-container { height: 100vh; background: #f0f2f5; }
.app-header { display: flex; align-items: center; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 0 20px; }
.logo { display: flex; align-items: center; gap: 8px; margin-right: 40px; font-size: 20px; font-weight: bold; }
.nav-menu { flex: 1; border-bottom: none !important; }
</style>
