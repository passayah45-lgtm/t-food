import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 text-center">
      <div>
        <p className="text-8xl font-bold text-gray-100">404</p>
        <h1 className="text-2xl font-semibold text-gray-800 mt-2">Page not found</h1>
        <p className="text-gray-500 mt-2 mb-6">The page you're looking for doesn't exist.</p>
        <Link to="/" className="btn-primary">Back to home</Link>
      </div>
    </div>
  )
}
