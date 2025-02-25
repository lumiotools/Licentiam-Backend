import type { FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface LicenseEntryFormProps {
  onSubmit: (formData: FormData) => void
  isLoading: boolean
}

export function LicenseEntryForm({ onSubmit, isLoading }: LicenseEntryFormProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)

    // Convert the date to MM/DD/YYYY format
    const birthDateInput = formData.get("birth_date") as string
    if (birthDateInput) {
      const date = new Date(birthDateInput)
      const formattedDate = `${(date.getMonth() + 1).toString().padStart(2, "0")}/${date.getDate().toString().padStart(2, "0")}/${date.getFullYear()}`
      formData.set("birth_date", formattedDate)
    }

    onSubmit(formData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-md">
      <div>
        <Label htmlFor="username">Username</Label>
        <Input id="username" name="username" required />
      </div>
      <div>
        <Label htmlFor="birth_date">Birth Date</Label>
        <Input id="birth_date" name="birth_date" type="date" required />
      </div>
      <div>
        <Label htmlFor="email">Email</Label>
        <Input id="email" name="email" type="email" required />
      </div>
      <div>
        <Label htmlFor="phone">Phone</Label>
        <Input id="phone" name="phone" type="tel" required />
      </div>
      <Button type="submit" disabled={isLoading}>
        {isLoading ? "Creating Entry..." : "Create Entry"}
      </Button>
    </form>
  )
}

