import { createContext, useContext, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'

const STORAGE_KEY = 'tfood.currentLocation'

const LocationContext = createContext(null)

const readStoredLocation = () => {
  if (typeof window === 'undefined') return null
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    if (!value) return null
    const parsed = JSON.parse(value)
    if (
      typeof parsed.latitude !== 'number' ||
      typeof parsed.longitude !== 'number'
    ) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function LocationProvider({ children }) {
  const [currentLocation, setCurrentLocation] = useState(readStoredLocation)
  const [detecting, setDetecting] = useState(false)
  const [error, setError] = useState('')

  const saveLocation = location => {
    setCurrentLocation(location)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(location))
    }
  }

  const detectLocation = () => {
    setError('')
    if (!navigator.geolocation) {
      const message = 'Location is not supported by this browser.'
      setError(message)
      toast.error(message)
      return
    }

    setDetecting(true)
    navigator.geolocation.getCurrentPosition(
      position => {
        const nextLocation = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          detectedAt: new Date().toISOString(),
        }
        saveLocation(nextLocation)
        setDetecting(false)
        toast.success('Location detected')
      },
      geolocationError => {
        const message = geolocationError.code === geolocationError.PERMISSION_DENIED
          ? 'Location permission was denied. You can still search without it.'
          : 'Could not detect your location. Please try again.'
        setError(message)
        setDetecting(false)
        toast.error(message)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    )
  }

  const clearLocation = () => {
    setCurrentLocation(null)
    setError('')
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  }

  const value = useMemo(() => ({
    currentLocation,
    detecting,
    error,
    detectLocation,
    clearLocation,
    hasLocation: Boolean(currentLocation),
  }), [currentLocation, detecting, error])

  return (
    <LocationContext.Provider value={value}>
      {children}
    </LocationContext.Provider>
  )
}

export function useLocationContext() {
  const value = useContext(LocationContext)
  if (!value) {
    throw new Error('useLocationContext must be used inside LocationProvider')
  }
  return value
}
