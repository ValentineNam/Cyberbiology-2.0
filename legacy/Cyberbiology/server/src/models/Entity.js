class Entity {
  constructor(x, y) {
    this.id = Symbol('entity');
    this.x = x;
    this.y = y;
    this.objType = 'base';
    this.energy = [0, 100]; // [current, max]
    this.minerals = [0, 100]; // [current, max]
    this.age = [0, 100]; // [current, max]
    this.flagAlive = 1;
  }

  update() {
    // Базовая логика обновления
  }

  die() {
    this.flagAlive = 0;
  }

  // Методы для проверки параметров
  getEnergyLevel() {
    return Math.floor((this.energy[0] / this.energy[1]) * 10);
  }

  getMineralsLevel() {
    return Math.floor((this.minerals[0] / this.minerals[1]) * 10);
  }

  getAgeLevel() {
    return Math.floor((this.age[0] / this.age[1]) * 10);
  }
}

module.exports = Entity;