import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createRealtimeClient, getStoredAccessToken } from '../lib/realtime'

export function useRealtime({
  enabled = true,
  tokenProvider = getStoredAccessToken,
  onMessage,
} = {}) {
  const onMessageRef = useRef(onMessage)
  const [snapshot, setSnapshot] = useState({
    status: 'idle',
    isConnected: false,
    isFallback: false,
  })
  const [lastMessage, setLastMessage] = useState(null)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const client = useMemo(
    () => createRealtimeClient({ tokenProvider }),
    [tokenProvider],
  )

  const connect = useCallback(() => client.connect(), [client])
  const disconnect = useCallback(() => client.disconnect(), [client])

  useEffect(() => {
    const unsubscribe = client.subscribe(event => {
      if (event.kind === 'status') {
        setSnapshot(event.snapshot)
        return
      }
      if (event.kind === 'message') {
        setLastMessage(event.message)
        onMessageRef.current?.(event.message)
      }
    })

    if (enabled) {
      client.connect()
      setSnapshot(client.getSnapshot())
    } else {
      client.disconnect()
      setSnapshot(client.getSnapshot())
    }

    return () => {
      unsubscribe()
      client.disconnect()
    }
  }, [client, enabled])

  return {
    ...snapshot,
    lastMessage,
    connect,
    disconnect,
  }
}

export default useRealtime
