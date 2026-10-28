import { createRouter, createWebHistory } from 'vue-router'
import AdminView from '../views/AdminView.vue'
import TestingView from '../views/TestingView.vue'
import ComparisonView from '@/views/ComparisonView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/comparison' }, // Default to Comparison if no path is given
    { path: '/admin', name: 'admin', component: AdminView },
    { path: '/testing', name: 'testing', component: TestingView },
    {
      path: '/comparison',
      name: 'Comparison',
      component: ComparisonView
    }
  ]
})

export default router