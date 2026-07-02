import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export default function Footer() {
  const { t } = useTranslation()
  const paymentMethods = [
    'Visa / Mastercard',
    'PayPal',
    'UPI / Razorpay',
    'Wave',
    'Orange Money',
    t('footer.cashOnDelivery'),
  ]

  return (
    <footer className="bg-gray-900 text-gray-400 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-10">
          <div className="col-span-2 md:col-span-1">
            <Link to="/about" className="flex items-center gap-2 text-white font-bold text-xl mb-3 hover:text-white">
              T-Food
            </Link>
            <p className="text-sm leading-relaxed">
              {t('footer.tagline')}
            </p>
          </div>
          <div>
            <h4 className="text-white text-sm font-semibold mb-3">{t('footer.company')}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link to="/about" className="hover:text-white transition-colors">{t('footer.about')}</Link></li>
              <li><Link to="/careers" className="hover:text-white transition-colors">{t('footer.careers')}</Link></li>
              <li><Link to="/blog" className="hover:text-white transition-colors">{t('footer.blog')}</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white text-sm font-semibold mb-3">{t('footer.forPartners')}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link to="/become-rider" className="hover:text-white transition-colors">{t('footer.becomeRider')}</Link></li>
              <li><Link to="/partner-restaurant" className="hover:text-white transition-colors">{t('footer.addRestaurant')}</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="text-white text-sm font-semibold mb-3">{t('footer.support')}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link to="/help" className="hover:text-white transition-colors">{t('footer.helpCentre')}</Link></li>
              <li><Link to="/privacy" className="hover:text-white transition-colors">{t('footer.privacyPolicy')}</Link></li>
              <li><Link to="/terms" className="hover:text-white transition-colors">{t('footer.termsOfService')}</Link></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-800 pt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap gap-2 text-xs">
            {paymentMethods.map(method => (
              <span key={method} className="bg-gray-800 px-2.5 py-1 rounded-md">{method}</span>
            ))}
          </div>
          <p className="text-xs">&copy; {new Date().getFullYear()} T-Food. {t('footer.rights')}</p>
        </div>
      </div>
    </footer>
  )
}
