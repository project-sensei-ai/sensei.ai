export function BrandLogo({ className = 'h-8 w-auto' }: { className?: string }) {
  return (
    <>
      <img src="/lightLogo.png" alt="Sensei" className={`${className} dark:hidden`} />
      <img src="/darkLogo.png" alt="Sensei" className={`hidden dark:block ${className}`} />
    </>
  )
}