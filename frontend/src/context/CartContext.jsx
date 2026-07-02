import { createContext, useContext, useState, useEffect } from 'react'
import toast from 'react-hot-toast'

const CartContext = createContext(null)

const optionSignature = options => options.map(option => option.id).sort((a, b) => a - b).join('-')
const lineIdFor = (foodId, options = []) => `${foodId}:${optionSignature(options)}`

const normalizeCart = items => items.map(item => ({
  ...item,
  lineId: item.lineId || lineIdFor(item.id, item.options || []),
  optionIds: item.optionIds || (item.options || []).map(option => option.id),
}))

export function CartProvider({ children }) {
  const [items, setItems] = useState(() => {
    try { return normalizeCart(JSON.parse(localStorage.getItem('cart') || '[]')) } catch { return [] }
  })
  const [restaurantId, setRestaurantId] = useState(() =>
    localStorage.getItem('cart_restaurant') || null
  )

  useEffect(() => {
    localStorage.setItem('cart', JSON.stringify(items))
    if (restaurantId) localStorage.setItem('cart_restaurant', restaurantId)
    else localStorage.removeItem('cart_restaurant')
  }, [items, restaurantId])

  const addItem = (food, restId, options = []) => {
    // Prevent mixing items from different restaurants
    if (restaurantId && restaurantId !== String(restId)) {
      toast.error('Your cart has items from another restaurant. Clear it first.')
      return false
    }
    setRestaurantId(String(restId))
    setItems(prev => {
      const lineId = lineIdFor(food.id, options)
      const existing = prev.find(i => i.lineId === lineId)
      if (existing) return prev.map(i => i.lineId === lineId ? { ...i, qty: i.qty + 1 } : i)
      const optionTotal = options.reduce((sum, option) => sum + Number(option.price_delta), 0)
      return [...prev, {
        id: food.id,
        lineId,
        name: food.food_name,
        basePrice: parseFloat(food.food_price),
        price: parseFloat(food.food_price) + optionTotal,
        image: food.image || null,
        options,
        optionIds: options.map(option => option.id),
        qty: 1,
      }]
    })
    toast.success(`${food.food_name} added`)
    return true
  }

  const removeItem  = lineId => setItems(prev => prev.filter(i => i.lineId !== lineId))
  const increaseQty = lineId => setItems(prev => prev.map(i => i.lineId === lineId ? { ...i, qty: i.qty + 1 } : i))
  const decreaseQty = lineId => setItems(prev => {
    const item = prev.find(i => i.lineId === lineId)
    if (item?.qty <= 1) return prev.filter(i => i.lineId !== lineId)
    return prev.map(i => i.lineId === lineId ? { ...i, qty: i.qty - 1 } : i)
  })
  const clearCart   = () => { setItems([]); setRestaurantId(null) }
  const replaceCart = (foods, restId) => {
    setRestaurantId(String(restId))
    setItems(foods.map(food => ({
      id: food.id,
      lineId: lineIdFor(food.id, food.options || []),
      name: food.food_name,
      basePrice: parseFloat(food.food_price),
      price: parseFloat(food.food_price) + (food.options || []).reduce((sum, option) => sum + Number(option.price_delta), 0),
      image: food.image || null,
      options: food.options || [],
      optionIds: (food.options || []).map(option => option.id),
      qty: food.quantity,
    })))
  }

  const totalItems  = items.reduce((s, i) => s + i.qty, 0)
  const totalAmount = items.reduce((s, i) => s + i.price * i.qty, 0)

  return (
    <CartContext.Provider value={{ items, restaurantId, addItem, replaceCart, removeItem, increaseQty, decreaseQty, clearCart, totalItems, totalAmount }}>
      {children}
    </CartContext.Provider>
  )
}

export const useCart = () => {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within CartProvider')
  return ctx
}
