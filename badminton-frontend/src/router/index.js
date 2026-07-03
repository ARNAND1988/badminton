import { createRouter, createWebHistory } from 'vue-router'
import Register from '../components/Register.vue'
import Dashboard from '../components/Dashboard.vue'
import NotFound from '../components/NotFound.vue'
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
    meta: { navLabel: 'My Invoices', requiresAuth: true }
  },
  {
    path: '/admin/bookings',
    name: 'admin-bookings',
    component: Dashboard,
    props: { initialView: 'admin-bookings' },
    meta: { navLabel: 'Manage Bookings', requiresAuth: true }
  },
  {
    path: '/admin/courts',
    name: 'admin-courts',
    component: Dashboard,
    props: { initialView: 'admin-courts' },
    meta: { navLabel: 'Manage Courts', requiresAuth: true }
  },
  {
    path: '/admin/costs',
    name: 'admin-costs',
    component: Dashboard,
    props: { initialView: 'admin-costs' },
    meta: { navLabel: 'Split Costs', requiresAuth: true }
  },
  {
    path: '/admin/notifications',
    name: 'notifications',
    component: Dashboard,
    props: { initialView: 'notifications' },
    meta: { navLabel: 'Notifications', requiresAuth: true }
  },
  {
    path: '/admin/members',
    name: 'members',
    component: Dashboard,
    props: { initialView: 'members' },
    meta: { navLabel: 'Members', requiresAuth: true }
  },
  {
    path: '/notifications',
    redirect: '/admin/notifications'
  },
  {
    path: '/members',
    redirect: '/admin/members'
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFound,
    meta: { navLabel: 'Not Found' }
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
