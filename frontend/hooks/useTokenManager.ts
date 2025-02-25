"use client"

import { useState, useEffect } from "react"

interface Tokens {
  pdcToken: string
  crmToken: string
}

export function useTokenManager() {
  const [tokens, setTokens] = useState<Tokens | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTokens = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/get-token`)
        if (!response.ok) {
          throw new Error("Failed to fetch tokens")
        }
        const data: Tokens = await response.json()
        setTokens(data)
        localStorage.setItem("tokens", JSON.stringify(data))
        localStorage.setItem("loginTime", Date.now().toString())
      } catch (err) {
        setError(err instanceof Error ? err.message : "An unknown error occurred")
      } finally {
        setIsLoading(false)
      }
    }

    const storedTokens = localStorage.getItem("tokens")
    const loginTime = localStorage.getItem("loginTime")

    if (storedTokens && loginTime) {
      const parsedTokens = JSON.parse(storedTokens)
      const elapsedTime = Date.now() - Number.parseInt(loginTime)
      const thirtyMinutesInMs = 30 * 60 * 1000

      if (elapsedTime < thirtyMinutesInMs) {
        setTokens(parsedTokens)
      } else {
        fetchTokens()
      }
    } else {
      fetchTokens()
    }
  }, [])

  return { tokens, isLoading, error }
}

