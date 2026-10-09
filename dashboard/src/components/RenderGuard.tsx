import { Component, type ReactNode } from 'react'

interface RenderGuardProps {
  children: ReactNode
  fallback: ReactNode
}

interface RenderGuardState {
  failed: boolean
}

export class RenderGuard extends Component<RenderGuardProps, RenderGuardState> {
  state: RenderGuardState = { failed: false }

  static getDerivedStateFromError(): RenderGuardState {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback
    }
    return this.props.children
  }
}
