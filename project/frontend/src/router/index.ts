import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/live', name: 'LiveRoom', component: () => import('@/views/LiveRoom.vue') },
]

export default createRouter({ history: createWebHistory(), routes })
