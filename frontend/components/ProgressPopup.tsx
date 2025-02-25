import { Progress } from "@/components/ui/progress"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"

interface ProgressData {
  progress: number
  step: string
  message: string
  userId?: string
}

interface ProgressPopupProps {
  isOpen: boolean
  progressData: ProgressData | null
}

export function ProgressPopup({ isOpen, progressData }: ProgressPopupProps) {
  return (
    <Dialog open={isOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Creating License Entry</DialogTitle>
        </DialogHeader>
        {progressData && (
          <div className="mt-4">
            <Progress value={progressData.progress} className="w-full" />
            <p className="mt-2">{progressData.message}</p>
            {progressData.step === "complete" && progressData.userId && (
              <p className="mt-2 font-semibold">Provider {progressData.userId} is created in CRM</p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

