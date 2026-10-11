import React from 'react'
import './InfoPanel.css'

const InfoPanel = ({ selectedCell, worldInfo }) => {
  return (
    <div className="info-panel">
      <h3>Информация</h3>
      
      {worldInfo && (
        <div className="world-info">
          <h4>Мир</h4>
          <div className="info-item">
            <span>Шаг:</span>
            <span>{worldInfo.time}</span>
          </div>
          <div className="info-item">
            <span>Энергия:</span>
            <span>{Math.round(worldInfo.energy)}</span>
          </div>
          <div className="info-item">
            <span>Размер:</span>
            <span>{worldInfo.width}×{worldInfo.height}</span>
          </div>
        </div>
      )}
      
      {selectedCell && (
        <div className="cell-info">
          <h4>Клетка ({selectedCell.x}, {selectedCell.y})</h4>
          {selectedCell.entity ? (
            <>
              <div className="info-item">
                <span>Тип:</span>
                <span>{selectedCell.entity.objType}</span>
              </div>
              <div className="info-item">
                <span>Энергия:</span>
                <span>{selectedCell.entity.energy?.[0]} / {selectedCell.entity.energy?.[1]}</span>
              </div>
              <div className="info-item">
                <span>Возраст:</span>
                <span>{selectedCell.entity.age?.[0]} / {selectedCell.entity.age?.[1]}</span>
              </div>
              
              {selectedCell.entity.objType === 'bot' && selectedCell.entity.genom && (
                <div className="info-item">
                  <span>Геном:</span>
                  <div className="genom-display">
                    {selectedCell.entity.genom.slice(0, 10).join(', ')}...
                  </div>
                </div>
              )}
              
              {selectedCell.entity.direction && (
                <div className="info-item">
                  <span>Направление:</span>
                  <span>{selectedCell.entity.direction}</span>
                </div>
              )}
            </>
          ) : (
            <div className="info-item">
              <span>Пусто</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default InfoPanel