import { useEffect } from 'react'

const DEFAULT_TITLE = 'T-Food Global | Local Commerce Marketplace'

export default function useTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} | T-Food Global` : DEFAULT_TITLE
  }, [title])
}
