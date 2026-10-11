import React, { useRef, useEffect, useCallback } from 'react'
import './WorldCanvas.css'

const CELL_SIZE = 15

const WorldCanvas = ({ state, onSelectCell, onAddBot }) => {
  const canvasRef = useRef(null)

  const drawWorld = useCallback((ctx, worldData) => {
    if (!worldData) return

    const { grid, width, height } = worldData
    
    ctx.clearRect(0, 0, width * CELL_SIZE, height * CELL_SIZE)
    
    // Рисуем сетку
    ctx.strokeStyle = 'rgba(240, 240, 240, 0.1)'
    ctx.lineWidth = 0.5
    
    for (let x = 0; x <= width; x++) {
      ctx.beginPath()
      ctx.moveTo(x * CELL_SIZE, 0)
      ctx.lineTo(x * CELL_SIZE, height * CELL_SIZE)
      ctx.stroke()
    }
    
    for (let y = 0; y <= height; y++) {
      ctx.beginPath()
      ctx.moveTo(0, y * CELL_SIZE)
      ctx.lineTo(width * CELL_SIZE, y * CELL_SIZE)
      ctx.stroke()
    }

    // Рисуем сущности
    for (let x = 0; x < width; x++) {
      for (let y = 0; y < height; y++) {
        const cell = grid[x][y]
        if (cell) {
          drawEntity(ctx, cell, x, y)
        }
      }
    }
  }, [])

  const drawEntity = (ctx, entity, x, y) => {
    const cellX = x * CELL_SIZE
    const cellY = y * CELL_SIZE
    
    ctx.fillStyle = entity.color || '#ccc'
    
    switch (entity.objType) {
      case 'bot':
        // Рисуем бота как круг с направлением
        ctx.beginPath()
        ctx.arc(
          cellX + CELL_SIZE / 2,
          cellY + CELL_SIZE / 2,
          CELL_SIZE / 2 - 1,
          0,
          2 * Math.PI
        )
        ctx.fill()
        
        // Направление бота
        if (entity.direction) {
          const centerX = cellX + CELL_SIZE / 2
          const centerY = cellY + CELL_SIZE / 2
          const radius = CELL_SIZE / 3
          
          let angle
          switch (entity.direction) {
            case 1: angle = -Math.PI / 2; break // вверх
            case 2: angle = -Math.PI / 4; break // вверх-вправо
            case 3: angle = 0; break           // вправо
            case 4: angle = Math.PI / 4; break // вниз-вправо
            case 5: angle = Math.PI / 2; break // вниз
            case 6: angle = 3 * Math.PI / 4; break // вниз-влево
            case 7: angle = Math.PI; break     // влево
            case 8: angle = -3 * Math.PI / 4; break // вверх-влево
            default: angle = 0
          }
          
          ctx.strokeStyle = '#fff'
          ctx.lineWidth = 2
          ctx.beginPath()
          ctx.moveTo(centerX, centerY)
          ctx.lineTo(
            centerX + Math.cos(angle) * radius,
            centerY + Math.sin(angle) * radius
          )
          ctx.stroke()
        }
        break
        
      case 'plant':
        // Рисуем растение как квадрат
        ctx.fillRect(cellX + 1, cellY + 1, CELL_SIZE - 2, CELL_SIZE - 2)
        break
        
      case 'mineral':
        // Рисуем минерал как серый квадрат
        ctx.fillRect(cellX + 2, cellY + 2, CELL_SIZE - 4, CELL_SIZE - 4)
        break
        
      default:
        // Пустая клетка
        break
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !state) return

    const ctx = canvas.getContext('2d')
    canvas.width = state.width * CELL_SIZE
    canvas.height = state.height * CELL_SIZE

    drawWorld(ctx, state)
  }, [state, drawWorld])

  const handleClick = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    
    const cellX = Math.floor(x / CELL_SIZE)
    const cellY = Math.floor(y / CELL_SIZE)
    
    if (state && cellX >= 0 && cellX < state.width && cellY >= 0 && cellY < state.height) {
      const clickedCell = state.grid[cellX][cellY]
      onSelectCell({
        x: cellX,
        y: cellY,
        entity: clickedCell
      })
    }
  }

  return (
    <div className="world-canvas-wrapper">
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        className="world-canvas"
        style={{
          maxWidth: '100%',
          maxHeight: '80vh'
        }}
      />
    </div>
  )
}

export default WorldCanvas