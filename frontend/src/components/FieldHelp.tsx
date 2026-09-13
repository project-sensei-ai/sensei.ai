import { CircleHelp } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/** Small inline "i" button that explains a form field in a tooltip. */
export default function FieldHelp({ text, className = '' }: { text: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          tabIndex={-1}
          className={`inline-flex items-center text-muted-foreground transition-colors hover:text-foreground ${className}`}
          aria-label="What goes here"
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-xs text-xs font-normal leading-relaxed">
        {text}
      </TooltipContent>
    </Tooltip>
  )
}