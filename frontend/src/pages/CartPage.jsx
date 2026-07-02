import { Link } from 'react-router-dom'
import { Minus, Plus, ShoppingCart, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useCart } from '../context/CartContext'
import useTitle from '../hooks/useTitle'

export default function CartPage() {
  const { t } = useTranslation()
  useTitle(t('cart.title'))
  const { items, increaseQty, decreaseQty, removeItem, clearCart, totalAmount, totalItems } = useCart()

  if (!items.length) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <ShoppingCart size={42} className="text-gray-300 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-gray-950">{t('cart.emptyTitle')}</h1>
        <p className="text-gray-500 mt-2">{t('cart.emptyBody')}</p>
        <Link to="/search" className="btn-primary inline-flex mt-6">{t('cart.browseRestaurants')}</Link>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-950">{t('cart.title')}</h1>
          <p className="text-gray-500 mt-1">{t('cart.readyForCheckout', { count: totalItems })}</p>
        </div>
        <button onClick={clearCart} className="btn-secondary text-sm">{t('common.clear')}</button>
      </div>

      <div className="grid lg:grid-cols-[1fr_280px] gap-6">
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.lineId} className="card p-4 flex items-center gap-4">
              {item.image && <img src={item.image} alt="" className="h-14 w-14 rounded-lg object-cover flex-shrink-0" />}
              <div className="flex-1 min-w-0">
                <h2 className="font-semibold text-gray-950">{item.name}</h2>
                {!!item.options?.length && <p className="text-xs text-gray-500 mt-1">{item.options.map(option => `${option.group}: ${option.name}`).join(' · ')}</p>}
                <p className="text-sm text-gray-500">{t('cart.eachPrice', { price: item.price.toFixed(2) })}</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => decreaseQty(item.lineId)} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50"><Minus size={14} /></button>
                <span className="w-8 text-center text-sm font-medium">{item.qty}</span>
                <button onClick={() => increaseQty(item.lineId)} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50"><Plus size={14} /></button>
              </div>
              <p className="w-20 text-right font-semibold">Rs. {(item.price * item.qty).toFixed(2)}</p>
              <button onClick={() => removeItem(item.lineId)} className="p-2 rounded-lg text-red-500 hover:bg-red-50"><Trash2 size={16} /></button>
            </div>
          ))}
        </div>

        <aside className="card p-5 h-fit">
          <h2 className="font-semibold text-gray-950 mb-4">{t('cart.summary')}</h2>
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>{t('cart.subtotal')}</span>
            <span>Rs. {totalAmount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm text-gray-600 mb-4">
            <span>{t('cart.delivery')}</span>
            <span>{t('cart.calculatedNext')}</span>
          </div>
          <div className="border-t border-gray-100 pt-4 flex justify-between font-semibold">
            <span>{t('cart.total')}</span>
            <span>Rs. {totalAmount.toFixed(2)}</span>
          </div>
          <Link to="/checkout" className="btn-primary w-full mt-5 block text-center">
            {t('cart.continueToCheckout')}
          </Link>
        </aside>
      </div>
    </div>
  )
}
