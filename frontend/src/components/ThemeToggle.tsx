import { useTheme } from '@/theme/ThemeProvider'
import { IconButton } from './IconButton'
import { SunIcon, MoonIcon } from './icons'

export function ThemeToggle() {
  const { resolved, toggle } = useTheme()
  const nextIsDark = resolved === 'light'
  return (
    <IconButton
      label={nextIsDark ? 'Switch to dark theme' : 'Switch to light theme'}
      onClick={toggle}
    >
      {resolved === 'dark' ? (
        <SunIcon className="h-5 w-5" />
      ) : (
        <MoonIcon className="h-5 w-5" />
      )}
    </IconButton>
  )
}
