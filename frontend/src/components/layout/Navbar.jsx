import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bell, Camera, ShoppingCart, Menu, X, MapPin, Search, LogOut, Package, Bike, Store, Settings, ShieldCheck, User, Heart, CircleHelp, Globe2 } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../context/AuthContext'
import { useLocationContext } from '../../context/LocationContext'
import { usePreferences } from '../../context/PreferencesContext'
import { LANGUAGE_OPTIONS } from '../../i18n'
import { getUnreadNotifications } from '../../api/notifications'

export default function Navbar({ cartCount = 0 }) {
  const { t } = useTranslation()
  const { user, role, logout } = useAuth()
  const { preferences, setLanguage } = usePreferences()
  const { currentLocation, detecting, detectLocation } = useLocationContext()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread'],
    queryFn: async () => (await getUnreadNotifications()).data,
    enabled: Boolean(user),
    refetchInterval: 15000,
  })
  const unreadCount = unreadData?.unread_count || 0
  const locationLabel = detecting
    ? t('nav.detecting')
    : currentLocation ? t('nav.locationDetected') : t('nav.detectLocation')
  const activeLanguages = LANGUAGE_OPTIONS.filter(option => option.is_active)

  const handleLogout = async () => {
    await logout()
    toast.success(t('common.logOut'))
    navigate('/login')
  }

  const goToAbout = () => {
    setMobileOpen(false)
    setUserMenuOpen(false)
  }

  const submitSearch = event => {
    event.preventDefault()
    const next = new URLSearchParams()
    const value = searchQuery.trim()
    if (value) next.set('q', value)
    if (currentLocation?.latitude && currentLocation?.longitude) {
      next.set('latitude', currentLocation.latitude)
      next.set('longitude', currentLocation.longitude)
    }
    setMobileOpen(false)
    const target = `/search${next.toString() ? `?${next.toString()}` : ''}`
    navigate(target)
  }

  return (
    <header className="bg-white border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <a href="/about" onClick={goToAbout} className="flex items-center gap-2 font-bold text-xl text-brand-600 flex-shrink-0">
            <span>T-Food</span>
          </a>

          <button
            type="button"
            onClick={detectLocation}
            disabled={detecting}
            className="hidden md:flex items-center gap-1.5 text-sm text-gray-600 bg-gray-50 hover:bg-gray-100 px-3 py-2 rounded-lg transition-colors border border-gray-200 disabled:opacity-70"
            title={currentLocation ? t('nav.updateCurrentLocation') : t('nav.detectCurrentLocation')}
          >
            <MapPin size={14} className="text-brand-500" />
            <span className="max-w-[140px] truncate">{locationLabel}</span>
          </button>

          <form onSubmit={submitSearch} className="hidden md:flex flex-1 max-w-sm mx-4 relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            <input
              value={searchQuery}
              onChange={event => setSearchQuery(event.target.value)}
              placeholder={t('nav.searchPlaceholder')}
              className="w-full pl-9 pr-10 py-2 text-sm border border-gray-200 rounded-xl bg-gray-50 focus:bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition-all"
              aria-label={t('nav.searchAria')}
            />
            <button
              type="submit"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-brand-600 flex items-center justify-center"
              title={t('common.search')}
              aria-label={t('common.search')}
            >
              <Search size={15} />
            </button>
          </form>

          <div className="flex items-center gap-2">
            <Link
              to="/search"
              className="hidden md:inline-flex items-center gap-1.5 p-2 hover:bg-gray-100 rounded-xl transition-colors text-gray-700 hover:text-brand-600"
              title={t('search.searchByImage')}
              aria-label={t('search.searchByImage')}
            >
              <Camera size={20} />
            </Link>
            {user ? (
              <>
                <Link to="/notifications" className="relative p-2 hover:bg-gray-100 rounded-xl transition-colors" title={t('nav.notifications')}>
                  <Bell size={20} className="text-gray-700" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs font-bold h-4 min-w-4 px-0.5 flex items-center justify-center rounded-full">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </Link>
                {role === 'customer' && (
                  <Link to="/cart" className="relative p-2 hover:bg-gray-100 rounded-xl transition-colors">
                    <ShoppingCart size={20} className="text-gray-700" />
                    {cartCount > 0 && (
                      <span className="absolute -top-0.5 -right-0.5 bg-brand-500 text-white text-xs font-bold h-4 w-4 flex items-center justify-center rounded-full">
                        {cartCount > 9 ? '9+' : cartCount}
                      </span>
                    )}
                  </Link>
                )}

                <div className="relative z-50">
                  <button
                    onClick={() => setUserMenuOpen(v => !v)}
                    className="flex items-center gap-2 p-1.5 hover:bg-gray-100 rounded-xl transition-colors"
                  >
                    <div className="h-8 w-8 rounded-full bg-brand-100 flex items-center justify-center">
                      <span className="text-sm font-semibold text-brand-700">
                        {user.first_name?.[0] || user.username[0]}
                      </span>
                    </div>
                    <span className="hidden sm:inline text-sm font-medium text-gray-700 max-w-[80px] truncate">
                      {user.first_name || user.username}
                    </span>
                  </button>

                  {userMenuOpen && (
                    <div className="absolute right-0 top-12 w-48 card py-1 shadow-lg">
                      {role === 'customer' && (
                        <Link
                          to="/favorites"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <Heart size={15} /> {t('nav.favorites')}
                        </Link>
                      )}
                      {role === 'customer' && (
                        <Link
                          to="/support"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <CircleHelp size={15} /> {t('nav.helpSupport')}
                        </Link>
                      )}
                      {role === 'customer' && (
                        <Link
                          to="/profile"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <User size={15} /> {t('nav.myProfile')}
                        </Link>
                      )}
                      {role !== 'customer' && (
                        <Link
                          to="/account"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <Settings size={15} /> {t('nav.accountSettings')}
                        </Link>
                      )}
                      <Link
                        to="/preferences"
                        className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                        onClick={() => setUserMenuOpen(false)}
                      >
                        <Settings size={15} /> {t('nav.preferences')}
                      </Link>
                      {role === 'customer' && (
                        <Link
                          to="/orders"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <Package size={15} /> {t('nav.myOrders')}
                        </Link>
                      )}
                      {role === 'partner' && (
                        <Link
                          to="/partner/dashboard"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <Bike size={15} /> {t('nav.partnerDashboard')}
                        </Link>
                      )}
                      {role === 'merchant' && (
                        <Link
                          to="/merchant/dashboard"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <Store size={15} /> {t('nav.merchantDashboard')}
                        </Link>
                      )}
                      {role === 'admin' && (
                        <Link
                          to="/operations"
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          <ShieldCheck size={15} /> {t('nav.operationsDashboard')}
                        </Link>
                      )}
                      <div className="border-t border-gray-100 my-1" />
                      <button
                        onClick={handleLogout}
                        className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 w-full text-left"
                      >
                        <LogOut size={15} /> {t('common.logOut')}
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <Link to="/preferences" className="btn-secondary py-2 px-3 text-sm hidden lg:inline-flex">{t('nav.preferences')}</Link>
                <Link to="/login" className="btn-secondary py-2 px-4 text-sm hidden sm:inline-flex">{t('common.signIn')}</Link>
                <Link to="/register" className="btn-primary py-2 px-4 text-sm">{t('common.signUp')}</Link>
              </div>
            )}

            <label className="hidden sm:flex items-center gap-1.5 text-xs text-gray-600">
              <Globe2 size={15} className="text-gray-500" />
              <span className="sr-only">{t('common.language')}</span>
              <select
                value={preferences.language}
                onChange={event => setLanguage(event.target.value)}
                className="bg-transparent border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-100"
                aria-label={t('common.language')}
              >
                {activeLanguages.map(language => (
                  <option key={language.code} value={language.code}>
                    {language.native_name}
                  </option>
                ))}
              </select>
            </label>

            <button onClick={() => setMobileOpen(v => !v)} className="p-2 hover:bg-gray-100 rounded-xl md:hidden">
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="md:hidden border-t border-gray-100 py-3 flex flex-col gap-1">
            <button
              type="button"
              onClick={detectLocation}
              disabled={detecting}
              className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-xl mb-2 text-left disabled:opacity-70"
            >
              <MapPin size={14} className="text-brand-500" />
              <span className="text-sm text-gray-600">{locationLabel}</span>
            </button>
            <form onSubmit={submitSearch} className="relative mb-2">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input
                value={searchQuery}
                onChange={event => setSearchQuery(event.target.value)}
                placeholder={t('nav.searchPlaceholderMobile')}
                className="w-full pl-9 pr-10 py-2 text-sm border border-gray-200 rounded-xl outline-none"
                aria-label={t('nav.searchAria')}
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-brand-600 flex items-center justify-center"
                title={t('common.search')}
                aria-label={t('common.search')}
              >
                <Search size={15} />
              </button>
            </form>
            <Link
              to="/search"
              className="flex items-center gap-2 px-3 py-2 bg-brand-50 text-brand-700 rounded-xl mb-2 text-sm font-medium"
              onClick={() => setMobileOpen(false)}
            >
              <Camera size={15} /> {t('search.searchByImage')}
            </Link>
            {!user && (
              <>
                <Link to="/preferences" className="btn-secondary py-2.5 text-center text-sm" onClick={() => setMobileOpen(false)}>{t('nav.preferences')}</Link>
                <Link to="/login" className="btn-secondary py-2.5 text-center text-sm" onClick={() => setMobileOpen(false)}>{t('common.signIn')}</Link>
                <Link to="/register" className="btn-primary py-2.5 text-center text-sm" onClick={() => setMobileOpen(false)}>{t('common.signUp')}</Link>
              </>
            )}
            <label className="flex sm:hidden items-center gap-2 px-3 py-2 bg-gray-50 rounded-xl text-sm text-gray-600">
              <Globe2 size={15} className="text-gray-500" />
              <span>{t('common.language')}</span>
              <select
                value={preferences.language}
                onChange={event => setLanguage(event.target.value)}
                className="ml-auto bg-transparent border border-gray-200 rounded-lg px-2 py-1 text-xs"
                aria-label={t('common.language')}
              >
                {activeLanguages.map(language => (
                  <option key={language.code} value={language.code}>
                    {language.native_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>

      {userMenuOpen && <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />}
    </header>
  )
}
