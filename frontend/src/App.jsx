import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import { LocationProvider } from './context/LocationContext'
import { PreferencesProvider } from './context/PreferencesContext'
import { RequireAuth, RequireGuest } from './components/layout/AuthGuard'
import MainLayout from './components/layout/MainLayout'
import Spinner from './components/ui/Spinner'

const lazyNamed = (loader, exportName) => lazy(() => (
  loader().then((module) => ({ default: module[exportName] }))
))

const CartPage = lazy(() => import('./pages/CartPage'))
const AccountPage = lazy(() => import('./pages/AccountPage'))
const CheckoutPage = lazy(() => import('./pages/CheckoutPage'))
const HomePage = lazy(() => import('./pages/HomePage'))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'))
const FavoritesPage = lazy(() => import('./pages/FavoritesPage'))
const GoogleAuthCallbackPage = lazy(() => import('./pages/GoogleAuthCallbackPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const MerchantDashboardPage = lazy(() => import('./pages/MerchantDashboardPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const OperationsDashboardPage = lazy(() => import('./pages/OperationsDashboardPage'))
const OrdersPage = lazy(() => import('./pages/OrdersPage'))
const OrderTrackingPage = lazy(() => import('./pages/OrderTrackingPage'))
const PartnerDashboardPage = lazy(() => import('./pages/PartnerDashboardPage'))
const PaymentPage = lazy(() => import('./pages/PaymentPage'))
const PreferencesPage = lazy(() => import('./pages/PreferencesPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'))
const RestaurantPage = lazy(() => import('./pages/RestaurantPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const SupportPage = lazy(() => import('./pages/SupportPage'))
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
    <div className="min-h-[50vh] flex items-center justify-center" aria-label={t('common.loading')}>
      <Spinner size="lg" />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <PreferencesProvider>
        <LocationProvider>
          <CartProvider>
          <Suspense fallback={<RouteLoadingFallback />}>
          <Routes>
          <Route path="/login" element={<RequireGuest><LoginPage /></RequireGuest>} />
          <Route path="/register" element={<RequireGuest><RegisterPage /></RequireGuest>} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
          <Route path="/auth/google/callback" element={<GoogleAuthCallbackPage />} />

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
          </CartProvider>
        </LocationProvider>
      </PreferencesProvider>
    </AuthProvider>
  )
}
