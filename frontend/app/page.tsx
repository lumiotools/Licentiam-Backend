"use client"

import { useEffect, useState } from "react"
import { useTokenManager } from "@/hooks/useTokenManager"
import { LicenseEntryForm } from "@/components/LicenseEntryForm"
import { ProgressPopup } from "@/components/ProgressPopup"

interface ProgressData {
  progress: number
  step: string
  message: string
  userId?: string
}

export default function Home() {
  const { tokens, isLoading: isTokenLoading, error: tokenError } = useTokenManager()
  const [message, setMessage] = useState<string>("")
  const [isCreatingLicense, setIsCreatingLicense] = useState(false)
  const [progressData, setProgressData] = useState<ProgressData | null>(null)

  useEffect(() => {
    if (isTokenLoading) {
      setMessage("Logging in to PDC and CRM...")
    } else if (tokenError) {
      setMessage("Error: " + tokenError)
    } else if (tokens) {
      setMessage("Logged in successfully!")
    }
  }, [isTokenLoading, tokenError, tokens])

  const handleCreateLicenseEntry = async (formData: FormData) => {
    if (!tokens) {
      setMessage("Error: No tokens available")
      return
    }

    setIsCreatingLicense(true)
    setProgressData(null)

    const body = {
      username: formData.get("username"),
      birth_date: formData.get("birth_date"),
      email: formData.get("email"),
      phone: formData.get("phone"),
      pdcToken: tokens.pdcToken,
      crmToken: tokens.crmToken,
    }

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/create-licence-entry`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        throw new Error("Failed to create license entry")
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error("No reader available")
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = new TextDecoder().decode(value)
        const lines = chunk.split("\n\n")
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            
            const data = JSON.parse(line.slice(6).replaceAll("'", '"'))
            
            setProgressData(data)
            if (data.step === "complete") {
              setMessage(`License created successfully! Provider ${data.userId} is created in CRM`)
            } else if (data.step === "error") {
              setMessage(data.message)
            }
          }
        }
      }
    } catch (error) {
      setMessage("Error: " + (error instanceof Error ? error.message : "An unknown error occurred"))
    } finally {
      setIsCreatingLicense(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-8">License Entry Creator</h1>
      <div className="text-xl mb-4">{message}</div>
      {tokens && <LicenseEntryForm onSubmit={handleCreateLicenseEntry} isLoading={isCreatingLicense} />}
      <ProgressPopup isOpen={isCreatingLicense} progressData={progressData} />
    </main>
  )
}

