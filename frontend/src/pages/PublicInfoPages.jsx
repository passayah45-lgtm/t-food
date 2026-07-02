import { Link, useNavigate } from 'react-router-dom'
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
  MapPin,
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

const companyValues = [
  'Local merchants should own the customer relationship, not disappear behind a marketplace.',
  'Customers should know who prepares, carries, and supports every order.',
  'Delivery partners should see fair, transparent work with clear pickup and payout information.',
  'Growth should start with operational reliability before expanding into more categories.',
]

const roadmapItems = [
  {
    icon: Store,
    title: 'Food',
    body: 'Restaurant discovery, menu accuracy, cash on delivery, preparation workflow, delivery tracking, support, and merchant analytics.',
  },
  {
    icon: ShoppingBasket,
    title: 'Grocery',
    body: 'Local grocery catalogs, item availability, substitutions, scheduled delivery, and neighborhood-first inventory visibility.',
  },
  {
    icon: Pill,
    title: 'Pharmacy',
    body: 'Trusted pharmacy storefronts, careful order handling, document-aware operations where required, and reliable customer support.',
  },
  {
    icon: PackageCheck,
    title: 'Courier',
    body: 'Local package pickup and drop-off for small businesses, students, families, and neighborhood commerce.',
  },
  {
    icon: Building2,
    title: 'Merchant Operating System',
    body: 'Tools for menus, stock, order flow, revenue, payouts, notifications, customer trust, and performance improvement.',
  },
  {
    icon: Lightbulb,
    title: 'AI Commerce',
    body: 'Future assistant tools for smarter search, merchant insights, support triage, demand planning, and safer marketplace operations.',
  },
]

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
      {items.map(item => (
        <article key={item.title} className="border border-gray-200 rounded-lg p-5">
          <div className="h-10 w-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center mb-4">
            <item.icon size={20} />
          </div>
          <h2 className="font-semibold text-gray-950">{item.title}</h2>
          <p className="text-sm text-gray-600 mt-2 leading-relaxed">{item.body}</p>
        </article>
      ))}
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
  const { user, role, logout } = useAuth()

  if (!user) {
    return <Link to="/register?role=merchant" className="btn-primary inline-flex">Add your restaurant</Link>
  }

  if (role === 'merchant') {
    return <Link to="/merchant/dashboard" className="btn-primary inline-flex">Open merchant dashboard</Link>
  }

  const signOutAndRegister = async () => {
    await logout()
    navigate('/register?role=merchant')
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3">
      <button type="button" onClick={signOutAndRegister} className="btn-primary inline-flex w-fit">
        Sign out and create merchant account
      </button>
      <p className="text-sm text-gray-500">
        You are signed in with a non-merchant account.
      </p>
    </div>
  )
}

function RiderSignupCta() {
  const navigate = useNavigate()
  const { user, role, logout } = useAuth()

  if (!user) {
    return <Link to="/register?role=partner" className="btn-primary inline-flex">Create rider account</Link>
  }

  if (role === 'partner') {
    return <Link to="/partner/dashboard" className="btn-primary inline-flex">Open rider dashboard</Link>
  }

  const signOutAndRegister = async () => {
    await logout()
    navigate('/register?role=partner')
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3">
      <button type="button" onClick={signOutAndRegister} className="btn-primary inline-flex w-fit">
        Sign out and create rider account
      </button>
      <p className="text-sm text-gray-500">
        You are signed in with a non-rider account.
      </p>
    </div>
  )
}

export function AboutPage() {
  return (
    <PageShell
      title="About T-Food"
      eyebrow="Company"
      description="T-Food is a marketplace and operating system for local commerce. We are starting with restaurant delivery, then expanding carefully into grocery, pharmacy, courier delivery, and merchant tools."
    >
      <div className="space-y-10">
        <section className="grid lg:grid-cols-[1.1fr_0.9fr] gap-5">
          <div className="border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-950">What is T-Food?</h2>
            <div className="mt-4 space-y-3 text-gray-700 leading-relaxed">
              <p>
                T-Food connects customers, restaurants, delivery partners, and operators in one trusted local marketplace. Customers discover nearby restaurants, merchants manage orders and menus, delivery partners claim eligible work, and operations teams keep the marketplace reliable.
              </p>
              <p>
                The company was founded by a Guinean entrepreneur with a global vision: build practical technology that helps local businesses grow first in one area, then one city, then many markets with the same discipline.
              </p>
            </div>
          </div>
          <div className="border border-gray-200 rounded-lg p-6 bg-gray-50">
            <h2 className="text-xl font-semibold text-gray-950">Why T-Food exists</h2>
            <p className="text-gray-700 mt-4 leading-relaxed">
              Many local businesses need more than a listing app. They need dependable order flow, verification, analytics, payout visibility, delivery coordination, and support. T-Food exists to make local commerce easier to trust and easier to operate.
            </p>
          </div>
        </section>

        <section className="grid md:grid-cols-2 gap-4">
          <article className="border border-gray-200 rounded-lg p-6">
            <Compass size={24} className="text-brand-600" />
            <h2 className="text-xl font-semibold text-gray-950 mt-4">Mission</h2>
            <p className="text-gray-700 mt-3 leading-relaxed">
              Help local merchants sell with confidence, help customers order with trust, and help delivery partners earn through clear, reliable marketplace operations.
            </p>
          </article>
          <article className="border border-gray-200 rounded-lg p-6">
            <Route size={24} className="text-brand-600" />
            <h2 className="text-xl font-semibold text-gray-950 mt-4">Vision</h2>
            <p className="text-gray-700 mt-3 leading-relaxed">
              Become a global local-commerce platform built from strong city-by-city operations, merchant-first tools, trusted delivery, and practical technology.
            </p>
          </article>
        </section>

        <InfoGrid
          items={[
            {
              icon: Store,
              title: 'Merchant benefits',
              body: 'Restaurants get storefront tools, menus, order workflow, analytics, payout visibility, notifications, verification, and a clearer path to daily growth.',
            },
            {
              icon: Bike,
              title: 'Delivery partner benefits',
              body: 'Partners get a simple dashboard for availability, order claims, pickup, delivery status, earnings visibility, and trusted account verification.',
            },
            {
              icon: Users,
              title: 'Customer benefits',
              body: 'Customers get nearby restaurant discovery, simple checkout, order tracking, saved addresses, loyalty, support, and safer merchant visibility.',
            },
          ]}
        />

        <section className="border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-950">Five-year roadmap</h2>
          <p className="text-gray-600 mt-3 leading-relaxed">
            T-Food will grow in stages. The first priority is a reliable restaurant delivery marketplace in one city area. After the operating model is stable, the same platform foundation can support more local commerce categories.
          </p>
          <div className="grid md:grid-cols-3 gap-4 mt-6">
            {roadmapItems.map(item => (
              <article key={item.title} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <item.icon size={20} className="text-brand-600" />
                <h3 className="font-semibold text-gray-950 mt-3">{item.title}</h3>
                <p className="text-sm text-gray-600 mt-2 leading-relaxed">{item.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-gray-950">What we believe</h2>
          <div className="mt-5 space-y-3">
            {companyValues.map(value => (
              <p key={value} className="flex gap-3 text-gray-700">
                <CheckCircle2 size={18} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                <span>{value}</span>
              </p>
            ))}
          </div>
        </section>
      </div>
    </PageShell>
  )
}

export function CareersPage() {
  return (
    <PageShell
      title="Careers at T-Food"
      eyebrow="Careers"
      description="We are building the operating layer for local commerce. Early T-Food team members care about execution, field operations, merchants, delivery quality, and dependable software."
    >
      <div className="space-y-8">
        <InfoGrid
          items={[
            {
              icon: BriefcaseBusiness,
              title: 'Operations',
              body: 'Work with restaurants, delivery partners, customer issues, order quality, and day-to-day marketplace reliability.',
            },
            {
              icon: Handshake,
              title: 'Merchant success',
              body: 'Help local businesses onboard, build menus, understand analytics, and improve service performance.',
            },
            {
              icon: Building2,
              title: 'Product and engineering',
              body: 'Build tools for ordering, delivery, analytics, notifications, payments, and marketplace trust.',
            },
          ]}
        />
        <div className="border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold text-gray-950">Open applications</h2>
          <p className="text-gray-600 mt-2">
            T-Food is building its early pilot team around field execution, merchant support, delivery quality, customer care, and dependable software. We value people who can solve real operating problems, communicate clearly, and stay close to merchants and customers.
          </p>
          <p className="text-gray-600 mt-3">
            If you want to join early, contact the operations team through the Help Center with your role interest, location, availability, and relevant experience.
          </p>
          <Link to="/help" className="btn-primary inline-flex mt-5">Visit Help Center</Link>
        </div>
      </div>
    </PageShell>
  )
}

export function BlogPage() {
  const posts = [
    {
      title: 'Why T-Food starts with restaurant delivery',
      body: 'Restaurant delivery gives T-Food the most useful first marketplace loop: customers search, merchants prepare, partners deliver, and operations can measure quality from order creation to final delivery.',
    },
    {
      title: 'Building trust into marketplace operations',
      body: 'A marketplace becomes stronger when verification, document review, clear status updates, support tickets, and operational visibility are built before rapid expansion.',
    },
    {
      title: 'What merchants need beyond more orders',
      body: 'Restaurants need daily sales trends, order volume, menu controls, availability, payout visibility, notifications, prep-time monitoring, and performance signals they can act on.',
    },
    {
      title: 'How T-Food thinks about delivery partners',
      body: 'Delivery partners need fair access to available orders, clear pickup information, simple status updates, and a verification process that protects customers and merchants.',
    },
    {
      title: 'From food delivery to local commerce',
      body: 'The long-term T-Food platform can support groceries, pharmacy, courier work, and merchant software after the restaurant delivery operating model is proven.',
    },
    {
      title: 'Why pilot density matters',
      body: 'A focused pilot area helps T-Food learn faster, support restaurants better, reduce delivery friction, and build trust before entering more neighborhoods.',
    },
  ]
  return (
    <PageShell
      title="T-Food Blog"
      eyebrow="Updates"
      description="Notes from the T-Food team about marketplace operations, merchant growth, delivery quality, and local commerce."
    >
      <div className="grid md:grid-cols-3 gap-4">
        {posts.map(post => (
          <article key={post.title} className="border border-gray-200 rounded-lg p-5">
            <Newspaper size={22} className="text-brand-600" />
            <h2 className="font-semibold text-gray-950 mt-4">{post.title}</h2>
            <p className="text-sm text-gray-600 mt-2 leading-relaxed">{post.body}</p>
          </article>
        ))}
      </div>
    </PageShell>
  )
}

export function HelpCenterPage() {
  return (
    <PageShell
      title="Help Center"
      eyebrow="Support"
      description="Get help with customer orders, merchant onboarding, delivery partner approval, account access, refunds, and marketplace operations."
    >
      <div className="grid md:grid-cols-3 gap-4">
        <article className="border border-gray-200 rounded-lg p-5">
          <CircleHelp size={22} className="text-brand-600" />
          <h2 className="font-semibold text-gray-950 mt-4">Customers</h2>
          <p className="text-sm text-gray-600 mt-2">
            For order issues, missing items, payment questions, delivery updates, address problems, or refund requests. Customer support tickets are connected to your account so the team can see the right order history.
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            <Link to="/support" className="btn-secondary inline-flex">Open customer support</Link>
            <Link to="/login" className="btn-secondary inline-flex">Sign in</Link>
            <Link to="/register" className="btn-primary inline-flex">Create account</Link>
          </div>
        </article>
        <article className="border border-gray-200 rounded-lg p-5">
          <Store size={22} className="text-brand-600" />
          <h2 className="font-semibold text-gray-950 mt-4">Merchants</h2>
          <p className="text-sm text-gray-600 mt-2">For storefront setup, document verification, menu changes, order handling, payout questions, and restaurant readiness.</p>
          <Link to="/partner-restaurant" className="btn-secondary inline-flex mt-4">Partner with T-Food</Link>
        </article>
        <article className="border border-gray-200 rounded-lg p-5">
          <Bike size={22} className="text-brand-600" />
          <h2 className="font-semibold text-gray-950 mt-4">Delivery partners</h2>
          <p className="text-sm text-gray-600 mt-2">For account approval, identity documents, availability, pickup flow, delivery status, earnings, and account support.</p>
          <Link to="/become-rider" className="btn-secondary inline-flex mt-4">Become a rider</Link>
        </article>
      </div>
    </PageShell>
  )
}

export function PrivacyPolicyPage() {
  return (
    <PageShell
      title="Privacy Policy"
      eyebrow="Legal"
      description="This page explains the main types of information T-Food uses to operate ordering, delivery, merchant services, support, payments, safety, and account features."
    >
      <div className="prose prose-gray max-w-none">
        <h2>Information we collect</h2>
        <p>We collect account details, contact information, delivery addresses, order history, support requests, restaurant and delivery partner profile information, verification documents where required, device information, and location data when you choose to share it.</p>
        <h2>How we use information</h2>
        <p>We use information to create accounts, process orders, calculate serviceability, support delivery tracking, notify users, operate merchant dashboards, manage partner verification, handle support tickets, prevent abuse, and improve T-Food.</p>
        <h2>Verification documents</h2>
        <p>Merchant and delivery partner documents are used for account review, trust, safety, and operations approval. Customers may upload a profile photo, but customer identity documents are not required for normal ordering.</p>
        <h2>Location data</h2>
        <p>Location is used to show nearby restaurants, validate delivery distance, help partners find pickups, and improve delivery status. Browser location is optional and can be denied or cleared by the user.</p>
        <h2>Payments and providers</h2>
        <p>Payment information may be processed by external payment providers. T-Food stores payment status, method, provider references, and transaction identifiers needed for order support and reconciliation.</p>
        <h2>Contact</h2>
        <p>For privacy questions, contact T-Food operations through the Help Center.</p>
      </div>
    </PageShell>
  )
}

export function TermsPage() {
  return (
    <PageShell
      title="Terms of Service"
      eyebrow="Legal"
      description="These terms describe the basic responsibilities of customers, merchants, delivery partners, and T-Food when using the marketplace."
    >
      <div className="prose prose-gray max-w-none">
        <h2>Using T-Food</h2>
        <p>Users agree to provide accurate account, address, contact, merchant, and delivery information. T-Food may restrict accounts that abuse support, payments, orders, delivery flow, or marketplace trust.</p>
        <h2>Orders and delivery</h2>
        <p>Restaurants are responsible for menu accuracy, preparation, packaging, and readiness. Delivery partners are responsible for pickup, safe transport, timely status updates, and delivery confirmation.</p>
        <h2>Payments and refunds</h2>
        <p>Cash on delivery and online payments may be available depending on market configuration. Refunds are reviewed through support and may depend on order status, merchant settlement, payment status, and operational evidence.</p>
        <h2>Merchant and partner verification</h2>
        <p>Merchant and delivery partner accounts may require T-Food approval before public selling or delivery work. T-Food may pause accounts for safety, quality, fraud, or operational reasons.</p>
        <h2>Platform changes</h2>
        <p>T-Food may improve features, pricing, policies, delivery rules, and market availability as the platform grows.</p>
      </div>
    </PageShell>
  )
}

export function BecomeRiderPage() {
  return (
    <PageShell
      title="Become a T-Food Rider"
      eyebrow="Delivery partners"
      description="Deliver with T-Food, claim eligible orders, update delivery progress, and help local customers receive orders with confidence."
    >
      <div className="space-y-8">
        <StepList
          steps={[
            { title: 'Create your account', body: 'Register as a delivery partner with your name, email, and secure password.' },
            { title: 'Upload profile photo', body: 'Add a clear partner profile photo from your dashboard. This helps merchants, customers, and operations identify the approved delivery partner.' },
            { title: 'Upload ID, passport, or license', body: 'Submit one accepted identity document, passport, or driving license. Vehicle documents are optional when available.' },
            { title: 'Wait for approval', body: 'T-Food operations reviews your profile and documents before live delivery work is enabled. Rejection reasons appear in your dashboard if anything needs correction.' },
            { title: 'Set availability', body: 'After approval, use the partner dashboard to go available when you are ready to receive delivery opportunities.' },
            { title: 'Claim delivery orders', body: 'View available pickups, claim one order at a time, mark pickup, update on-the-way status, and confirm delivery.' },
          ]}
        />
        <RiderSignupCta />
      </div>
    </PageShell>
  )
}

export function PartnerRestaurantPage() {
  return (
    <PageShell
      title="Partner Restaurant"
      eyebrow="For merchants"
      description="Bring your restaurant to T-Food with a storefront, menu controls, order workflow, analytics, payout visibility, and delivery readiness tools."
    >
      <div className="space-y-8">
        <InfoGrid
          items={[
            {
              icon: FileText,
              title: 'Build your storefront',
              body: 'Create your restaurant profile, add contact details, set delivery radius, pin pickup location, and upload a cover image.',
            },
            {
              icon: ShieldCheck,
              title: 'Get verified',
              body: 'Upload an owner profile photo, one accepted identity document, and restaurant photos. Your storefront becomes public after operations approval.',
            },
            {
              icon: HeartHandshake,
              title: 'Operate daily',
              body: 'Accept orders, manage item availability, monitor analytics, view notifications, and track payout status.',
            },
          ]}
        />
        <StepList
          steps={[
            { title: 'Register as merchant', body: 'Create a merchant account and complete your business profile.' },
            { title: 'Upload owner photo', body: 'Add a clear owner profile photo from the merchant verification panel so operations can identify the responsible account owner.' },
            { title: 'Upload identity document', body: 'Submit one accepted identity document such as a national ID, passport, or voter card.' },
            { title: 'Upload restaurant photo', body: 'Add restaurant photos so T-Food can review storefront readiness and marketplace trust.' },
            { title: 'Wait for approval', body: 'T-Food operations reviews your account and documents before public selling is enabled. Rejection reasons are shown clearly if anything needs correction.' },
            { title: 'Create storefront', body: 'Add your restaurant profile, address, service settings, operating hours, images, and pickup details.' },
            { title: 'Add menu', body: 'Create menu items, prices, options, availability, and preparation details from the merchant dashboard.' },
            { title: 'Start receiving orders', body: 'Once verified, customers can discover your restaurant and your team can manage orders from the dashboard.' },
          ]}
        />
        <MerchantSignupCta />
      </div>
    </PageShell>
  )
}
