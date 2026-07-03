import { createRouter, createWebHistory } from 'vue-router'
import Register from '../components/Register.vue'
import Dashboard from '../components/Dashboard.vue'
import { hasAuthSession } from '../authSession'

const routes = [
  {
    path: '/',
    redirect: '/availability'
  },
  {
    path: '/login',
    name: 'login',
    component: Register,
    meta: { navLabel: 'Login' }
  },
  {
    path: '/dashboard',
    redirect: '/availability'
  },
  {
    path: '/bookings',
    name: 'bookings',
    component: Dashboard,
    props: { initialView: 'bookings' },
    meta: { navLabel: 'Bookings' }
  },
  {
    path: '/availability',
    name: 'availability',
    component: Dashboard,
    props: { initialView: 'availability' },
    meta: { navLabel: 'Play Availability' }
  },
  {
    path: '/costs',
    name: 'costs',
    component: Dashboard,
    props: { initialView: 'costs' },
    meta: { navLabel: 'Misc Costs', requiresAuth: true }
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: Dashboard,
    props: { initialView: 'notifications' },
    meta: { navLabel: 'Notifications', requiresAuth: true }
  },
  {
    path: '/members',
    name: 'members',
    component: Dashboard,
    props: { initialView: 'members' },
    meta: { navLabel: 'Members' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !hasAuthSession()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
