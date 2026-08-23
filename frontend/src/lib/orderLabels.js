export const orderDisplayCode = order => (
  order?.merchant_order_code || order?.order_code || order?.order_display_code || order?.order_id || order?.id
)

export const orderDisplayLabel = (order, t) => {
  const code = orderDisplayCode(order)
  if (!code) return t('orders.orderNumber', { id: '' })
  return order?.merchant_order_code || order?.order_code || order?.order_display_code
    ? `Order ${code}`
    : t('orders.orderNumber', { id: code })
}
