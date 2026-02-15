import { createRouter, createWebHistory } from 'vue-router'
import Register from '../components/Register.vue'
import Verify from '../components/Verify.vue'

const routes = [
  { path: '/', component: Register },
  { path: '/verify', component: Verify }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
