import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Bike,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  CircleHelp,
  Compass,
  FileText,
  Handshake,
  HeartHandshake,
  Lightbulb,
  Newspaper,
  PackageCheck,
  Pill,
  Route,
  ShieldCheck,
  ShoppingBasket,
  Store,
  Users,
} from 'lucide-react'
import useTitle from '../hooks/useTitle'
import { useAuth } from '../context/AuthContext'

const icons = {
  bike: Bike,
  briefcase: BriefcaseBusiness,
  building: Building2,
  compass: Compass,
  file: FileText,
  handshake: Handshake,
  heartHandshake: HeartHandshake,
  lightbulb: Lightbulb,
  newspaper: Newspaper,
  packageCheck: PackageCheck,
  pill: Pill,
  route: Route,
  shield: ShieldCheck,
  shoppingBasket: ShoppingBasket,
  store: Store,
  users: Users,
}

const translatedList = (t, key) => {
  const value = t(key, { returnObjects: true })
  return Array.isArray(value) ? value : []
}

function PageShell({ title, eyebrow, description, children }) {
  useTitle(title)
  return (
    <div className="bg-white">
      <section className="border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
          <p className="text-sm font-semibold text-brand-600">{eyebrow}</p>
          <h1 className="text-3xl sm:text-4xl font-bold text-gray-950 mt-3">{title}</h1>
          <p className="text-gray-600 mt-4 max-w-3xl leading-relaxed">{description}</p>
        </div>
      </section>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">{children}</div>
    </div>
  )
}

function InfoGrid({ items }) {
  return (
    <div className="grid md:grid-cols-3 gap-4">
      {items.map(item => {
        const Icon = icons[item.icon] || Store
        return (
          <article key={item.title} className="border border-gray-200 rounded-lg p-5">
            <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center mb-4">
              <Icon size={20} />
            </div>
            <h2 className="font-semibold text-gray-950">{item.title}</h2>
            <p className="text-sm text-gray-600 mt-2 leading-relaxed">{item.body}</p>
          </article>
        )
      })}
    </div>
  )
}

function StepList({ steps }) {
  return (
    <ol className="grid md:grid-cols-2 gap-4">
      {steps.map((step, index) => (
        <li key={step.title} className="border border-gray-200 rounded-lg p-5">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-white text-sm font-semibold">
            {index + 1}
          </span>
          <h2 className="font-semibold text-gray-950 mt-4">{step.title}</h2>
          <p className="text-sm text-gray-600 mt-2 leading-relaxed">{step.body}</p>
        </li>
      ))}
    </ol>
  )
}

function MerchantSignupCta() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { user, role, logout } = useAuth()

  if (!user) {
    return <Link to="/register?role=merchant" className="btn-primary inline-flex">{t('publicPages.cta.addRestaurant')}</Link>
  }

  if (role === 'merchant') {
    return <Link to="/merchant/dashboard" className="btn-primary inline-flex">{t('publicPages.cta.openMerchantDashboard')}</Link>
  }

  const signOutAndRegister = async () => {
    await logout()
    navigate('/register?role=merchant')
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3">
      <button type="button" onClick={signOutAndRegister} className="btn-primary inline-flex w-fit">
        {t('publicPages.cta.signOutMerchant')}
      </button>
      <p className="text-sm text-gray-500">
        {t('publicPages.cta.nonMerchantAccount')}
      </p>
    </div>
  )
}

function RiderSignupCta() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { user, role, logout } = useAuth()

  if (!user) {
    return <Link to="/register?role=partner" className="btn-primary inline-flex">{t('publicPages.cta.createRiderAccount')}</Link>
  }

  if (role === 'partner') {
    return <Link to="/partner/dashboard" className="btn-primary inline-flex">{t('publicPages.cta.openRiderDashboard')}</Link>
  }

  const signOutAndRegister = async () => {
    await logout()
    navigate('/register?role=partner')
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3">
      <button type="button" onClick={signOutAndRegister} className="btn-primary inline-flex w-fit">
        {t('publicPages.cta.signOutRider')}
      </button>
      <p className="text-sm text-gray-500">
        {t('publicPages.cta.nonRiderAccount')}
      </p>
    </div>
  )
}

function TranslatedPage({ pageKey, children }) {
  const { t } = useTranslation()
  return (
    <PageShell
      title={t(`publicPages.${pageKey}.title`)}
      eyebrow={t(`publicPages.${pageKey}.eyebrow`)}
      description={t(`publicPages.${pageKey}.description`)}
    >
      {children(t)}
    </PageShell>
  )
}

export function AboutPage() {
  return (
    <TranslatedPage pageKey="about">
      {t => (
        <div className="space-y-10">
          <section className="grid lg:grid-cols-[1.1fr_0.9fr] gap-5">
            <div className="border border-gray-200 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-gray-950">{t('publicPages.about.whatTitle')}</h2>
              <div className="mt-4 space-y-3 text-gray-700 leading-relaxed">
                {translatedList(t, 'publicPages.about.whatBody').map(paragraph => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </div>
            <div className="border border-gray-200 rounded-lg p-6 bg-gray-50">
              <h2 className="text-xl font-semibold text-gray-950">{t('publicPages.about.whyTitle')}</h2>
              <p className="text-gray-700 mt-4 leading-relaxed">{t('publicPages.about.whyBody')}</p>
            </div>
          </section>

          <section className="grid md:grid-cols-2 gap-4">
            <article className="border border-gray-200 rounded-lg p-6">
              <Compass size={24} className="text-brand-600" />
              <h2 className="text-xl font-semibold text-gray-950 mt-4">{t('publicPages.about.missionTitle')}</h2>
              <p className="text-gray-700 mt-3 leading-relaxed">{t('publicPages.about.missionBody')}</p>
            </article>
            <article className="border border-gray-200 rounded-lg p-6">
              <Route size={24} className="text-brand-600" />
              <h2 className="text-xl font-semibold text-gray-950 mt-4">{t('publicPages.about.visionTitle')}</h2>
              <p className="text-gray-700 mt-3 leading-relaxed">{t('publicPages.about.visionBody')}</p>
            </article>
          </section>

          <InfoGrid items={translatedList(t, 'publicPages.about.benefits')} />

          <section className="border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-950">{t('publicPages.about.roadmapTitle')}</h2>
            <p className="text-gray-600 mt-3 leading-relaxed">{t('publicPages.about.roadmapBody')}</p>
            <div className="grid md:grid-cols-3 gap-4 mt-6">
              {translatedList(t, 'publicPages.about.roadmapItems').map(item => {
                const Icon = icons[item.icon] || Store
                return (
                  <article key={item.title} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                    <Icon size={20} className="text-brand-600" />
                    <h3 className="font-semibold text-gray-950 mt-3">{item.title}</h3>
                    <p className="text-sm text-gray-600 mt-2 leading-relaxed">{item.body}</p>
                  </article>
                )
              })}
            </div>
          </section>

          <section className="border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-950">{t('publicPages.about.beliefsTitle')}</h2>
            <div className="mt-5 space-y-3">
              {translatedList(t, 'publicPages.about.beliefs').map(value => (
                <p key={value} className="flex gap-3 text-gray-700">
                  <CheckCircle2 size={18} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                  <span>{value}</span>
                </p>
              ))}
            </div>
          </section>
        </div>
      )}
    </TranslatedPage>
  )
}

export function CareersPage() {
  return (
    <TranslatedPage pageKey="careers">
      {t => (
        <div className="space-y-8">
          <InfoGrid items={translatedList(t, 'publicPages.careers.areas')} />
          <div className="border border-gray-200 rounded-lg p-6">
            <h2 className="font-semibold text-gray-950">{t('publicPages.careers.openTitle')}</h2>
            {translatedList(t, 'publicPages.careers.openBody').map(paragraph => (
              <p key={paragraph} className="text-gray-600 mt-3">{paragraph}</p>
            ))}
            <Link to="/help" className="btn-primary inline-flex mt-5">{t('publicPages.careers.visitHelp')}</Link>
          </div>
        </div>
      )}
    </TranslatedPage>
  )
}

export function BlogPage() {
  return (
    <TranslatedPage pageKey="blog">
      {t => (
        <div className="grid md:grid-cols-3 gap-4">
          {translatedList(t, 'publicPages.blog.posts').map(post => (
            <article key={post.title} className="border border-gray-200 rounded-lg p-5">
              <Newspaper size={22} className="text-brand-600" />
              <h2 className="font-semibold text-gray-950 mt-4">{post.title}</h2>
              <p className="text-sm text-gray-600 mt-2 leading-relaxed">{post.body}</p>
            </article>
          ))}
        </div>
      )}
    </TranslatedPage>
  )
}

export function HelpCenterPage() {
  return (
    <TranslatedPage pageKey="help">
      {t => (
        <div className="grid md:grid-cols-3 gap-4">
          {translatedList(t, 'publicPages.help.cards').map(card => {
            const Icon = icons[card.icon] || CircleHelp
            return (
              <article key={card.title} className="border border-gray-200 rounded-lg p-5">
                <Icon size={22} className="text-brand-600" />
                <h2 className="font-semibold text-gray-950 mt-4">{card.title}</h2>
                <p className="text-sm text-gray-600 mt-2">{card.body}</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  {(card.links || []).map(link => (
                    <Link key={link.to} to={link.to} className={link.primary ? 'btn-primary inline-flex' : 'btn-secondary inline-flex'}>
                      {link.label}
                    </Link>
                  ))}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </TranslatedPage>
  )
}

function LegalPage({ pageKey }) {
  return (
    <TranslatedPage pageKey={pageKey}>
      {t => (
        <div className="prose prose-gray max-w-none">
          {translatedList(t, `publicPages.${pageKey}.sections`).map(section => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              <p>{section.body}</p>
            </section>
          ))}
        </div>
      )}
    </TranslatedPage>
  )
}

export function PrivacyPolicyPage() {
  return <LegalPage pageKey="privacy" />
}

export function TermsPage() {
  return <LegalPage pageKey="terms" />
}

export function BecomeRiderPage() {
  return (
    <TranslatedPage pageKey="becomeRider">
      {t => (
        <div className="space-y-8">
          <StepList steps={translatedList(t, 'publicPages.becomeRider.steps')} />
          <RiderSignupCta />
        </div>
      )}
    </TranslatedPage>
  )
}

export function PartnerRestaurantPage() {
  return (
    <TranslatedPage pageKey="partnerRestaurant">
      {t => (
        <div className="space-y-8">
          <InfoGrid items={translatedList(t, 'publicPages.partnerRestaurant.features')} />
          <StepList steps={translatedList(t, 'publicPages.partnerRestaurant.steps')} />
          <MerchantSignupCta />
        </div>
      )}
    </TranslatedPage>
  )
}
