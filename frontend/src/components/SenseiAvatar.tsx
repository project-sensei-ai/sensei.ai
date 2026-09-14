/**
 * The colleague's face. One mark, used everywhere it speaks — chat, meetings,
 * onboarding — so the person always knows who is talking.
 */
export function SenseiAvatar({ size = 'md', pulse = false }: { size?: 'sm' | 'md' | 'lg'; pulse?: boolean }) {
  const px = size === 'sm' ? 'h-7 w-7 text-xs' : size === 'lg' ? 'h-12 w-12 text-lg' : 'h-9 w-9 text-sm'
  return (
    <span className={`relative inline-flex shrink-0 ${px}`}>
      {pulse && <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />}
      <span
        className={`relative inline-flex ${px} items-center justify-center rounded-full font-semibold text-white shadow-sm`}
        style={{ background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 55%, #ec4899 100%)' }}
        aria-label="Sensei"
      >
        S
      </span>
    </span>
  )
}
