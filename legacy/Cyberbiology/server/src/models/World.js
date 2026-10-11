const Bot = require('./Bot');
const Plant = require('./Plant');
const Mineral = require('./Mineral');

class World {
  constructor(width, height) {
    this.width = width;
    this.height = height;
    this.grid = Array.from({ length: width }, () => Array(height).fill(null));
    this.entities = new Map(); // ID -> entity
    this.worldEnergy = width * height * 512; // как в оригинале
    this.worldTime = 0;
    this.GRID_SIZE = 15;
  }

  getEntity(x, y) {
    if (x >= 0 && x < this.width && y >= 0 && y < this.height) {
      return this.grid[x][y];
    }
    return null;
  }

  setEntity(x, y, entity) {
    if (x >= 0 && x < this.width && y >= 0 && y < this.height) {
      this.grid[x][y] = entity;
      if (entity && entity.id) {
        this.entities.set(entity.id, entity);
      }
    }
  }

  removeEntity(x, y) {
    if (x >= 0 && x < this.width && y >= 0 && y < this.height) {
      const entity = this.grid[x][y];
      if (entity && entity.id) {
        this.entities.delete(entity.id);
      }
      this.grid[x][y] = null;
    }
  }

  isEmpty(x, y) {
    return this.getEntity(x, y) === null;
  }

  getWorldState() {
    return {
      grid: this.grid.map(row => row.map(cell => cell ? {
        objType: cell.objType,
        x: cell.x,
        y: cell.y,
        energy: cell.energy,
        age: cell.age,
        ...(cell.genom && { genom: cell.genom }),
        ...(cell.color && { color: cell.color }),
        ...(cell.direction && { direction: cell.direction })
      } : null)),
      worldEnergy: this.worldEnergy,
      worldTime: this.worldTime,
      width: this.width,
      height: this.height
    };
  }
}

module.exports = World;