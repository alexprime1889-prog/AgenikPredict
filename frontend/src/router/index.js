import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import LoginView from '../views/LoginView.vue'
import AuthVerifyView from '../views/AuthVerifyView.vue'
import { isAuthenticated } from '../store/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { public: true }
  },
  {
    path: '/auth/verify',
    name: 'AuthVerify',
    component: AuthVerifyView,
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Auth guard: redirect to /login if not authenticated
router.beforeEach((to, from, next) => {
  if (to.meta.public) {
    // Public routes (login, verify) — skip auth check
    // If already logged in and going to login, redirect to home
    if (to.name === 'Login' && isAuthenticated.value) {
      return next('/')
    }
    return next()
  }

  if (!isAuthenticated.value) {
    return next('/login')
  }

  next()
})

export default router
