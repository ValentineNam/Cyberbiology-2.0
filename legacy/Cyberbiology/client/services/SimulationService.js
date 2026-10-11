class SimulationService {
  constructor() {
    this.ws = null
    this.onConnectCallback = null
    this.onDisconnectCallback = null
    this.onUpdateCallback = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.hostname}:3000`
    
    try {
      this.ws = new WebSocket(wsUrl)
      
      this.ws.onopen = () => {
        console.log('Connected to simulation server')
        this.reconnectAttempts = 0
        if (this.onConnectCallback) {
          this.onConnectCallback()
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'UPDATE' || data.type === 'INIT') {
            if (this.onUpdateCallback) {
              this.onUpdateCallback(data.data)
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      this.ws.onclose = () => {
        console.log('Disconnected from simulation server')
        if (this.onDisconnectCallback) {
          this.onDisconnectCallback()
        }
        
        // Попробовать переподключиться
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          setTimeout(() => {
            this.reconnectAttempts++
            this.connect()
          }, 1000 * this.reconnectAttempts)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error)
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  onConnect(callback) {
    this.onConnectCallback = callback
  }

  onDisconnect(callback) {
    this.onDisconnectCallback = callback
  }

  onUpdate(callback) {
    this.onUpdateCallback = callback
  }

  sendCommand(command, data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: command, data }))
    }
  }
}

export default SimulationService