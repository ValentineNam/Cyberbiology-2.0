class SimulationSocket {
  constructor(server) {
    const WebSocket = require('ws');
    this.wss = new WebSocket.Server({ server });
    this.clients = new Set();
    this.simulation = null;
  }

  init(simulation) {
    this.simulation = simulation;

    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      console.log('Client connected');

      // Отправляем начальное состояние мира
      if (this.simulation) {
        ws.send(JSON.stringify({
          type: 'INIT',
          data: this.simulation.getWorldState()
        }));
      }

      ws.on('message', (data) => {
        try {
          const message = JSON.parse(data);
          this.handleMessage(ws, message);
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      });

      ws.on('close', () => {
        this.clients.delete(ws);
        console.log('Client disconnected');
      });
    });
  }

  broadcast(message) {
    this.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify(message));
      }
    });
  }

  handleMessage(ws, message) {
    switch (message.type) {
      case 'CONTROL_START':
        this.simulation.start();
        break;
      case 'CONTROL_STOP':
        this.simulation.stop();
        break;
      case 'CONTROL_ADD_BOT':
        if (this.simulation) {
          this.simulation.addBot(message.data.x, message.data.y, message.data.genom);
        }
        break;
      case 'CONTROL_ADD_PLANT':
        if (this.simulation) {
          this.simulation.addPlant(message.data.x, message.data.y, message.data.genus);
        }
        break;
      case 'CONTROL_CLEAR':
        // Реализация очистки мира
        break;
      default:
        console.warn('Unknown message type:', message.type);
    }
  }

  updateClients() {
    if (this.simulation) {
      const state = this.simulation.getWorldState();
      this.broadcast({
        type: 'UPDATE',
        data: {
          ...state,
          running: this.simulation.running
        }
      });
    }
  }
}

module.exports = SimulationSocket;