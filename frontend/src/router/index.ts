import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '@/layouts/MainLayout.vue'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    admin?: boolean
    title?: string
  }
}

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    // 定向查看订单由页面在异步加载完成后滚动，避免覆盖目标位置。
    if (to.name === 'boarding' && to.query.order) return false
    return { left: 0, top: 0 }
  },
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: MainLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'pets',
          name: 'pets',
          component: () => import('@/views/PetsView.vue'),
          meta: { title: '宠物档案' },
        },
        {
          path: 'pets/:id',
          name: 'pet-detail',
          component: () => import('@/views/PetDetailView.vue'),
          meta: { title: '宠物详情' },
        },
        {
          path: 'boarding',
          name: 'boarding',
          component: () => import('@/views/BoardingView.vue'),
          meta: { title: '寄养预约' },
        },
        {
          path: 'agent',
          name: 'agent',
          component: () => import('@/views/AgentView.vue'),
          meta: { title: '智能助手' },
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
          meta: { title: '个人中心' },
        },
        {
          path: 'admin',
          name: 'admin',
          component: () => import('@/views/AdminView.vue'),
          meta: { title: '管理控制台', admin: true },
        },
      ],
    },
    {
      path: '/pay/:paymentNo',
      name: 'pay',
      component: () => import('@/views/PayView.vue'),
      meta: { public: true, title: '支付' },
    },
    {
      path: '/boarding/orders/:id/handover',
      name: 'handover',
      component: () => import('@/views/HandoverView.vue'),
      meta: { title: '寄养交接单' },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
  if (to.meta.admin && auth.user?.role !== 'admin') {
    return { name: 'dashboard' }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta.title ? `${to.meta.title} · PawCare` : 'PawCare'
  document.title = title
})

export default router
