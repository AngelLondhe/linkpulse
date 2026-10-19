import { Toaster } from 'sonner'
import { useTheme } from '../lib/theme'

export function ThemedToaster() {
  const { resolved } = useTheme()
  return <Toaster theme={resolved} position="bottom-right" richColors closeButton />
}
