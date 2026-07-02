import { Outlet } from 'react-router-dom'
import { useCart } from '../../context/CartContext'
import Footer from './Footer'
import Navbar from './Navbar'

export default function MainLayout() {
  const { totalItems } = useCart()

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar cartCount={totalItems} />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
