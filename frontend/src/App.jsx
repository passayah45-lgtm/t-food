import { Component, Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import { LocationProvider } from './context/LocationContext'
import { PreferencesProvider } from './context/PreferencesContext'
import { RequireAuth, RequireGuest } from './components/layout/AuthGuard'
import MainLayout from './components/layout/MainLayout'
import Spinner from './components/ui/Spinner'

const isDynamicImportError = error => {
  const message = String(error?.message || error || '')
  return message.includes('dynamically imported module')
    || message.includes('Importing a module script failed')
    || message.includes('ChunkLoadError')
}

const loadRoute = async loader => {
  try {
    const module = await loader()
    sessionStorage.removeItem('tfood-route-reload')
    return module
  } catch (error) {
    if (isDynamicImportError(error) && sessionStorage.getItem('tfood-route-reload') !== '1') {
      sessionStorage.setItem('tfood-route-reload', '1')
      window.location.reload()
      return new Promise(() => {})
    }
    throw error
  }
}

const lazyRoute = loader => lazy(() => loadRoute(loader))
const lazyNamed = (loader, exportName) => lazy(() => (
  loadRoute(loader).then((module) => ({ default: module[exportName] }))
))

const CartPage = lazyRoute(() => import('./pages/CartPage'))
const AccountPage = lazyRoute(() => import('./pages/AccountPage'))
const CheckoutPage = lazyRoute(() => import('./pages/CheckoutPage'))
const HomePage = lazyRoute(() => import('./pages/HomePage'))
const ForgotPasswordPage = lazyRoute(() => import('./pages/ForgotPasswordPage'))
const FavoritesPage = lazyRoute(() => import('./pages/FavoritesPage'))
const LoginPage = lazyRoute(() => import('./pages/LoginPage'))
const MerchantDashboardPage = lazyRoute(() => import('./pages/MerchantDashboardPage'))
const NotificationsPage = lazyRoute(() => import('./pages/NotificationsPage'))
const OperationsDashboardPage = lazyRoute(() => import('./pages/OperationsDashboardPage'))
const OrdersPage = lazyRoute(() => import('./pages/OrdersPage'))
const OrderTrackingPage = lazyRoute(() => import('./pages/OrderTrackingPage'))
const PartnerDashboardPage = lazyRoute(() => import('./pages/PartnerDashboardPage'))
const PaymentPage = lazyRoute(() => import('./pages/PaymentPage'))
const PreferencesPage = lazyRoute(() => import('./pages/PreferencesPage'))
const ProfilePage = lazyRoute(() => import('./pages/ProfilePage'))
const RegisterPage = lazyRoute(() => import('./pages/RegisterPage'))
const ResetPasswordPage = lazyRoute(() => import('./pages/ResetPasswordPage'))
const RestaurantPage = lazyRoute(() => import('./pages/RestaurantPage'))
const SearchPage = lazyRoute(() => import('./pages/SearchPage'))
const SupportPage = lazyRoute(() => import('./pages/SupportPage'))
const publicInfoLoader = () => import('./pages/PublicInfoPages')
const AboutPage = lazyNamed(publicInfoLoader, 'AboutPage')
const BecomeRiderPage = lazyNamed(publicInfoLoader, 'BecomeRiderPage')
const BlogPage = lazyNamed(publicInfoLoader, 'BlogPage')
const CareersPage = lazyNamed(publicInfoLoader, 'CareersPage')
const HelpCenterPage = lazyNamed(publicInfoLoader, 'HelpCenterPage')
const PartnerRestaurantPage = lazyNamed(publicInfoLoader, 'PartnerRestaurantPage')
const PrivacyPolicyPage = lazyNamed(publicInfoLoader, 'PrivacyPolicyPage')
const TermsPage = lazyNamed(publicInfoLoader, 'TermsPage')

function RouteLoadingFallback() {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 px-4 text-center" aria-label={t('common.loading')}>
      <Spinner size="lg" />
      <p className="text-sm font-medium text-gray-600">{t('common.loading')}</p>
    </div>
  )
}

class RouteErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    console.error('T-Food route failed to render', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="max-w-md rounded-lg border border-gray-200 bg-white p-6 text-center shadow-sm">
            <h1 className="text-xl font-semibold text-gray-950">T-Food could not load this page</h1>
            <p className="mt-2 text-sm text-gray-600">Please reload once. If it still happens, sign out and sign in again.</p>
            <button type="button" className="btn-primary mt-5" onClick={() => window.location.reload()}>
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <AuthProvider>
      <PreferencesProvider>
        <LocationProvider>
          <CartProvider>
          <RouteErrorBoundary>
          <Suspense fallback={<RouteLoadingFallback />}>
          <Routes>
          <Route path="/login" element={<RequireGuest><LoginPage /></RequireGuest>} />
          <Route path="/register" element={<RequireGuest><RegisterPage /></RequireGuest>} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />

          <Route element={<MainLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/careers" element={<CareersPage />} />
            <Route path="/blog" element={<BlogPage />} />
            <Route path="/help" element={<HelpCenterPage />} />
            <Route path="/privacy" element={<PrivacyPolicyPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/become-rider" element={<BecomeRiderPage />} />
            <Route path="/partner-restaurant" element={<PartnerRestaurantPage />} />
            <Route path="/restaurant/register" element={<PartnerRestaurantPage />} />
            <Route path="/preferences" element={<PreferencesPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/restaurants/:id" element={<RestaurantPage />} />
            <Route path="/cart" element={<RequireAuth><CartPage /></RequireAuth>} />
            <Route path="/checkout" element={<RequireAuth><CheckoutPage /></RequireAuth>} />
            <Route path="/orders" element={<RequireAuth><OrdersPage /></RequireAuth>} />
            <Route path="/orders/:id" element={<RequireAuth><OrderTrackingPage /></RequireAuth>} />
            <Route path="/orders/:id/payment" element={<RequireAuth><PaymentPage /></RequireAuth>} />
            <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
            <Route path="/account" element={<RequireAuth><AccountPage /></RequireAuth>} />
            <Route path="/notifications" element={<RequireAuth><NotificationsPage /></RequireAuth>} />
            <Route path="/favorites" element={<RequireAuth role="customer"><FavoritesPage /></RequireAuth>} />
            <Route path="/support" element={<RequireAuth role="customer"><SupportPage /></RequireAuth>} />

            <Route path="/partner/dashboard" element={<RequireAuth role="partner"><PartnerDashboardPage /></RequireAuth>} />
            <Route path="/merchant/dashboard" element={<RequireAuth role="merchant"><MerchantDashboardPage /></RequireAuth>} />
            <Route path="/operations" element={<RequireAuth role="admin"><OperationsDashboardPage /></RequireAuth>} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
          </Routes>
          </Suspense>
          </RouteErrorBoundary>
          </CartProvider>
        </LocationProvider>
      </PreferencesProvider>
    </AuthProvider>
  )
}
