import React, { useState, useEffect } from 'react'
import WorldCanvas from './components/WorldCanvas'
import ControlPanel from './components/ControlPanel'
import InfoPanel from './components/InfoPanel'
import SimulationService from './services/SimulationService'
import './App.css'

function App() {
  const [simulationState, setSimulationState] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [selectedCell, setSelectedCell] = useState(null)
  const [connectionStatus, setConnectionStatus] = useState('disconnected')

  useEffect(() => {
    const service = new SimulationService()

    service.onConnect(() => {
      setIsConnected(true)
      setConnectionStatus('connected')
    })

    service.onDisconnect(() => {
      setIsConnected(false)
      setConnectionStatus('disconnected')
    })

    service.onUpdate((data) => {
      setSimulationState(data)
    })

    service.connect()

    return () => {
      service.disconnect()
    }
  }, [])

  const handleStartStop = () => {
    fetch('/api/control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        action: simulationState?.running ? 'stop' : 'start'
      })
    })
  }

  const handleAddBot = (x, y) => {
    fetch('/api/add-bot', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        x,
        y
      })
    })
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Кибербиология - Симуляция</h1>
        <div className={`connection-status ${connectionStatus}`}>
          {connectionStatus === 'connected' ? 'Подключен' : 'Отсоединен'}
        </div>
      </header>
      
      <div className="app-content">
        <div className="canvas-container">
          <WorldCanvas 
            state={simulationState} 
            onSelectCell={setSelectedCell}
            onAddBot={handleAddBot}
          />
        </div>
        
        <div className="panel-container">
          <ControlPanel 
            onStartStop={handleStartStop}
            isRunning={simulationState?.running || false}
            isConnected={isConnected}
          />
          
          <InfoPanel 
            selectedCell={selectedCell}
            worldInfo={simulationState ? {
              time: simulationState.worldTime,
              energy: simulationState.worldEnergy,
              width: simulationState.width,
              height: simulationState.height
            } : null}
          />
        </div>
      </div>
    </div>
  )
}

export default App