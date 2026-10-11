const express = require('express');
const http = require('http');
const path = require('path');
const cors = require('cors');
const SimulationEngine = require('./src/core/SimulationEngine');
const SimulationSocket = require('./src/api/SimulationSocket');

class Server {
  constructor(port = 3000) {
    this.port = port;
    this.app = express();
    this.server = http.createServer(this.app);
    this.simulation = new SimulationEngine();
    this.socket = new SimulationSocket(this.server);
    
    this.setupMiddleware();
    this.setupRoutes();
    this.setupSocket();
  }

  setupMiddleware() {
    this.app.use(cors({
      origin: ['http://localhost:3001', 'http://localhost:5173', 'http://127.0.0.1:3001', 'http://127.0.0.1:5173'],
      credentials: true
    }));
    this.app.use(express.static(path.join(__dirname, '../client/public')));
    this.app.use(express.json());
  }

  setupRoutes() {
    // API endpoints
    this.app.get('/api/status', (req, res) => {
      res.json({
        running: this.simulation.running,
        worldTime: this.simulation.world.worldTime,
        worldEnergy: this.simulation.world.worldEnergy
      });
    });

    this.app.post('/api/control', (req, res) => {
      const { action } = req.body;
      switch (action) {
        case 'start':
          this.simulation.start();
          res.json({ status: 'started' });
          break;
        case 'stop':
          this.simulation.stop();
          res.json({ status: 'stopped' });
          break;
        default:
          res.status(400).json({ error: 'Unknown action' });
      }
    });
  }

  setupSocket() {
    this.socket.init(this.simulation);

    // Обновляем клиентов каждые 100ms
    setInterval(() => {
      this.socket.updateClients();
    }, 100);
  }

  start() {
    this.server.listen(this.port, () => {
      console.log(`Server running on http://localhost:${this.port}`);
    });
  }

  stop() {
    this.simulation.stop();
    this.server.close(() => {
      console.log('Server stopped');
    });
  }
}

// Запуск сервера, если файл запускается напрямую
if (require.main === module) {
  const server = new Server();
  server.start();
}

module.exports = Server; 