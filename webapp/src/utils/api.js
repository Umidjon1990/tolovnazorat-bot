import axios from 'axios'
import { getInitData } from './telegram'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const initData = getInitData()
  if (initData) {
    config.headers.Authorization = `tma ${initData}`
  }
  return config
})

export const coursesAPI = {
  getAll: () => api.get('/courses'),
  getById: (id) => api.get(`/courses/${id}`)
}

export const userAPI = {
  register: (data) => api.post('/user/register', data),
  selectCourse: (courseName) => api.post('/user/select-course', { course_name: courseName }),
  savePhone: (phone) => api.post('/user/phone', { phone }),
  submitPayment: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/user/payment', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getMe: () => api.get('/user/me'),
  getSubscription: () => api.get('/user/subscription')
}

export const adminAPI = {
  getStats: () => api.get('/admin/stats'),
  getPendingPayments: () => api.get('/admin/payments/pending'),
  getApprovedPayments: (limit = 10) => api.get(`/admin/payments/approved?limit=${limit}`),
  approvePayment: (data) => api.post('/admin/payment/approve', data),
  rejectPayment: (paymentId) => api.post('/admin/payment/reject', { payment_id: paymentId }),
  getGroups: () => api.get('/admin/groups')
}

export default api
