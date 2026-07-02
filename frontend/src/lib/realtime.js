const DEFAULT_PATH = '/ws/orders/'
const DEFAULT_MIN_RECONNECT_DELAY = 1000
const DEFAULT_MAX_RECONNECT_DELAY = 30000
const DEFAULT_HEARTBEAT_INTERVAL = 25000
const SOCKET_CONNECTING = 0
const SOCKET_OPEN = 1

export function getStoredAccessToken() {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem('access_token') || ''
}

export function buildRealtimeUrl(token, path = DEFAULT_PATH) {
  if (typeof window === 'undefined' || !token) return ''

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = new URL(path, `${protocol}//${window.location.host}`)
  url.searchParams.set('token', token)
  return url.toString()
}

export function createRealtimeClient(options = {}) {
  return new RealtimeClient(options)
}

export class RealtimeClient {
  constructor({
    tokenProvider = getStoredAccessToken,
    path = DEFAULT_PATH,
    minReconnectDelay = DEFAULT_MIN_RECONNECT_DELAY,
    maxReconnectDelay = DEFAULT_MAX_RECONNECT_DELAY,
    heartbeatInterval = DEFAULT_HEARTBEAT_INTERVAL,
    WebSocketImpl,
  } = {}) {
    this.tokenProvider = tokenProvider
    this.path = path
    this.minReconnectDelay = minReconnectDelay
    this.maxReconnectDelay = maxReconnectDelay
    this.heartbeatInterval = heartbeatInterval
    this.WebSocketImpl = WebSocketImpl
    this.socket = null
    this.status = 'idle'
    this.reconnectAttempts = 0
    this.shouldReconnect = true
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.listeners = new Set()
  }

  subscribe(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  connect() {
    if (this.socket?.readyState === SOCKET_OPEN) return true
    if (this.socket?.readyState === SOCKET_CONNECTING) return true

    const SocketImpl = (
      this.WebSocketImpl
      || (typeof window !== 'undefined' ? window.WebSocket : null)
    )
    const token = this.tokenProvider()
    if (!SocketImpl || !token) {
      this.setStatus('fallback')
      return false
    }

    const url = buildRealtimeUrl(token, this.path)
    if (!url) {
      this.setStatus('fallback')
      return false
    }

    this.shouldReconnect = true
    this.clearReconnectTimer()
    this.setStatus('connecting')

    try {
      this.socket = new SocketImpl(url)
    } catch (error) {
      this.emit({ kind: 'error', error })
      this.setStatus('fallback')
      this.scheduleReconnect()
      return false
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0
      this.setStatus('connected')
      this.startHeartbeat()
    }

    this.socket.onmessage = event => {
      const message = this.parseMessage(event.data)
      if (message) this.emit({ kind: 'message', message })
    }

    this.socket.onerror = error => {
      this.emit({ kind: 'error', error })
    }

    this.socket.onclose = event => {
      this.stopHeartbeat()
      this.socket = null
      if (event.code === 4401) {
        this.shouldReconnect = false
        this.setStatus('fallback')
      } else if (this.shouldReconnect) {
        this.setStatus('reconnecting')
        this.scheduleReconnect()
      } else {
        this.setStatus('closed')
      }
      this.emit({ kind: 'close', event })
    }

    return true
  }

  disconnect() {
    this.shouldReconnect = false
    this.clearReconnectTimer()
    this.stopHeartbeat()
    if (this.socket) {
      this.socket.close()
      this.socket = null
    } else {
      this.setStatus('closed')
    }
  }

  send(message) {
    if (this.socket?.readyState !== SOCKET_OPEN) return false
    this.socket.send(JSON.stringify(message))
    return true
  }

  getSnapshot() {
    return {
      status: this.status,
      isConnected: this.status === 'connected',
      isFallback: this.status === 'fallback' || this.status === 'reconnecting',
    }
  }

  parseMessage(raw) {
    try {
      return JSON.parse(raw)
    } catch {
      return null
    }
  }

  setStatus(status) {
    if (this.status === status) return
    this.status = status
    this.emit({ kind: 'status', status, snapshot: this.getSnapshot() })
  }

  emit(event) {
    this.listeners.forEach(listener => {
      try {
        listener(event)
      } catch {
        // Listener failures should never break the socket or REST fallback.
      }
    })
  }

  scheduleReconnect() {
    this.clearReconnectTimer()
    const delay = Math.min(
      this.minReconnectDelay * 2 ** this.reconnectAttempts,
      this.maxReconnectDelay,
    )
    this.reconnectAttempts += 1
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }

  clearReconnectTimer() {
    if (!this.reconnectTimer) return
    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  startHeartbeat() {
    this.stopHeartbeat()
    if (!this.heartbeatInterval) return
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' })
    }, this.heartbeatInterval)
  }

  stopHeartbeat() {
    if (!this.heartbeatTimer) return
    clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = null
  }
}
