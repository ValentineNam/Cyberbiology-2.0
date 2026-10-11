import React, { useState } from 'react'
import './ControlPanel.css'

const ControlPanel = ({ onStartStop, isRunning, isConnected }) => {
  const [botsCount, setBotsCount] = useState(10)
  const [treesCount, setTreesCount] = useState(5)
  const [bushCount, setBushCount] = useState(5)
  const [grassCount, setGrassCount] = useState(10)

  const handleGenerate = async () => {
    // Здесь будет вызов API для генерации
    console.log('Generating entities:', { botsCount, treesCount, bushCount, grassCount })
  }

  return (
    <div className="control-panel">
      <h3>Управление</h3>
      
      <div className="control-group">
        <button 
          onClick={onStartStop}
          disabled={!isConnected}
          className={`control-btn ${isRunning ? 'stop' : 'start'}`}
        >
          {isRunning ? 'Остановить' : 'Запустить'}
        </button>
      </div>
      
      <div className="control-group">
        <h4>Генерация</h4>
        <div className="input-group">
          <label>Боты:</label>
          <input 
            type="number" 
            value={botsCount}
            onChange={(e) => setBotsCount(parseInt(e.target.value) || 0)}
            min="0"
            max="1000"
          />
        </div>
        
        <div className="input-group">
          <label>Деревья:</label>
          <input 
            type="number" 
            value={treesCount}
            onChange={(e) => setTreesCount(parseInt(e.target.value) || 0)}
            min="0"
            max="1000"
          />
        </div>
        
        <div className="input-group">
          <label>Кусты:</label>
          <input 
            type="number" 
            value={bushCount}
            onChange={(e) => setBushCount(parseInt(e.target.value) || 0)}
            min="0"
            max="1000"
          />
        </div>
        
        <div className="input-group">
          <label>Трава:</label>
          <input 
            type="number" 
            value={grassCount}
            onChange={(e) => setGrassCount(parseInt(e.target.value) || 0)}
            min="0"
            max="1000"
          />
        </div>
        
        <button 
          onClick={handleGenerate}
          disabled={!isConnected}
          className="generate-btn"
        >
          Сгенерировать
        </button>
      </div>
      
      <div className="control-group">
        <h4>Настройки</h4>
        <div className="input-group">
          <label>Скорость:</label>
          <select defaultValue="normal">
            <option value="slow">Медленно</option>
            <option value="normal">Нормально</option>
            <option value="fast">Быстро</option>
            <option value="very-fast">Очень быстро</option>
          </select>
        </div>
      </div>
    </div>
  )
}

export default ControlPanel