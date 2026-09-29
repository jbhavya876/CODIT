import React, { useEffect, useRef } from 'react'

/**
 * Living 2D/3D Canvas Dependency Constellation
 * Interactive node-edge graph reacting to cursor motion with laser tethering and gentle drift.
 */
export default function HeroConstellation({ className = '', height = 360 }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId
    let width = (canvas.width = canvas.offsetWidth * window.devicePixelRatio || 800)
    let heightPx = (canvas.height = height * window.devicePixelRatio || 360)

    const handleResize = () => {
      if (!canvas) return
      width = canvas.width = canvas.offsetWidth * window.devicePixelRatio
      heightPx = canvas.height = height * window.devicePixelRatio
    }
    window.addEventListener('resize', handleResize)

    const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    // Generate constellation nodes
    const nodeTypes = [
      { type: 'Service', color: '#8CC8FF', label: 'svc-auth' },
      { type: 'Service', color: '#8CC8FF', label: 'svc-checkout' },
      { type: 'Database', color: '#5DE6A8', label: 'db-postgres' },
      { type: 'Database', color: '#5DE6A8', label: 'db-redis' },
      { type: 'API', color: '#FFB020', label: 'api-gateway' },
      { type: 'Library', color: '#818CF8', label: 'pyjwt' },
      { type: 'Library', color: '#818CF8', label: 'cryptography' },
      { type: 'Infrastructure', color: '#FF4A2B', label: 'ingress-alb' },
      { type: 'Service', color: '#8CC8FF', label: 'worker-audit' },
      { type: 'Database', color: '#5DE6A8', label: 'timescale' },
      { type: 'API', color: '#FFB020', label: 'webhook-handler' },
    ]

    const numNodes = nodeTypes.length
    const nodes = nodeTypes.map((meta, i) => ({
      ...meta,
      x: (0.15 + (i / numNodes) * 0.7) * width + (Math.random() - 0.5) * 60,
      y: (0.2 + (Math.sin(i * 1.5) * 0.3 + 0.3)) * heightPx,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      radius: meta.type === 'Database' || meta.type === 'Infrastructure' ? 6 : 4.5,
    }))

    // Mouse coordinates
    let mouse = { x: -1000, y: -1000 }
    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      mouse.x = (e.clientX - rect.left) * window.devicePixelRatio
      mouse.y = (e.clientY - rect.top) * window.devicePixelRatio
    }
    const onMouseLeave = () => {
      mouse.x = -1000
      mouse.y = -1000
    }

    canvas.addEventListener('mousemove', onMouseMove)
    canvas.addEventListener('mouseleave', onMouseLeave)

    const render = () => {
      ctx.clearRect(0, 0, width, heightPx)

      // Draw subtle background grid
      ctx.strokeStyle = 'rgba(42, 46, 53, 0.4)'
      ctx.lineWidth = 1
      const gridSize = 40 * window.devicePixelRatio
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, heightPx)
        ctx.stroke()
      }
      for (let y = 0; y < heightPx; y += gridSize) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
        ctx.stroke()
      }

      // Update positions
      if (!isReducedMotion) {
        nodes.forEach((node) => {
          node.x += node.vx
          node.y += node.vy

          if (node.x < 30 || node.x > width - 30) node.vx *= -1
          if (node.y < 30 || node.y > heightPx - 30) node.vy *= -1

          // Gentle mouse repulsion
          const dx = node.x - mouse.x
          const dy = node.y - mouse.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 120 * window.devicePixelRatio && dist > 0) {
            const force = (120 * window.devicePixelRatio - dist) / 120
            node.x += (dx / dist) * force * 1.5
            node.y += (dy / dist) * force * 1.5
          }
        })
      }

      // Draw edges between close nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x
          const dy = nodes[i].y - nodes[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          const maxDist = 180 * window.devicePixelRatio
          if (dist < maxDist) {
            const alpha = (1 - dist / maxDist) * 0.35
            ctx.strokeStyle = `rgba(140, 200, 255, ${alpha})`
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(nodes[i].x, nodes[i].y)
            ctx.lineTo(nodes[j].x, nodes[j].y)
            ctx.stroke()
          }
        }
      }

      // Draw cursor laser tether if mouse is inside canvas
      nodes.forEach((node) => {
        const dx = node.x - mouse.x
        const dy = node.y - mouse.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 160 * window.devicePixelRatio) {
          const alpha = (1 - dist / (160 * window.devicePixelRatio)) * 0.6
          ctx.strokeStyle = `rgba(212, 255, 58, ${alpha})`
          ctx.lineWidth = 1.2
          ctx.setLineDash([3, 3])
          ctx.beginPath()
          ctx.moveTo(mouse.x, mouse.y)
          ctx.lineTo(node.x, node.y)
          ctx.stroke()
          ctx.setLineDash([])
        }
      })

      // Draw nodes
      nodes.forEach((node) => {
        // Outer halo
        ctx.fillStyle = node.color + '22'
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.radius * 2.2, 0, Math.PI * 2)
        ctx.fill()

        // Inner solid node
        ctx.fillStyle = node.color
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
        ctx.fill()

        // Node label
        ctx.fillStyle = 'rgba(241, 245, 249, 0.75)'
        ctx.font = `${9 * window.devicePixelRatio}px "JetBrains Mono", monospace`
        ctx.fillText(node.label, node.x + node.radius + 4, node.y + 3)
      })

      animationFrameId = requestAnimationFrame(render)
    }

    render()

    return () => {
      window.removeEventListener('resize', handleResize)
      canvas.removeEventListener('mousemove', onMouseMove)
      canvas.removeEventListener('mouseleave', onMouseLeave)
      cancelAnimationFrame(animationFrameId)
    }
  }, [height])

  return (
    <div className={`relative w-full overflow-hidden rounded-xl border border-[#2A2E35] bg-[#0A0B0D] ${className}`}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: `${height}px` }}
        className="block cursor-crosshair"
      />
      <div className="absolute top-2.5 right-3 flex items-center gap-1.5 font-mono text-[9px] text-slate-500 uppercase tracking-widest pointer-events-none">
        <span className="h-1.5 w-1.5 rounded-full bg-laser-lime animate-pulse" />
        LIVING DEPENDENCY CONSTELLATION
      </div>
    </div>
  )
}
