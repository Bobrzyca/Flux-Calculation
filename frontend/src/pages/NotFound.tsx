import { useNavigate } from 'react-router-dom'
import { EmptyState, Button } from '@/components'

export function NotFound() {
  const navigate = useNavigate()
  return (
    <EmptyState
      title="Page not found"
      description="That screen doesn't exist. Head back to your analyses."
      action={<Button onClick={() => navigate('/')}>Back to analyses</Button>}
    />
  )
}
