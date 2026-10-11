const Entity = require('./Entity');

class Bot extends Entity {
  constructor(x, y, color = 'gray') {
    super(x, y);
    this.objType = 'bot';
    this.age = [0, 128];
    this.color = color;
    this.direction = 1; // 1-8 направления
    this.flagAttacked = [0, 0]; // [current turn, previous turn] - 1-8: direction, 0: not attacked
    this.flagSleeping = 0; // 1-10: sleeping, 0: not sleeping
    this.flagHungry = 0;
    this.flagMoved = 0;
    this.energy = [0, 1024];
    this.minerals = [0, 256];
    this.speed = 10;
    this.genom = [];
    this.paramsGenom = [];
    this.eatings = [0, 0, 0, 0]; // [plants, bots, meat, minerals]
  }

  // Методы поведения
  mutate() {
    const pos = Math.floor(Math.random() * this.genom.length);
    const oldGen = this.genom[pos];
    let newGen;
    do {
      newGen = Math.floor(Math.random() * 14); // 0-14 как в оригинале
    } while (newGen === oldGen);
    this.genom[pos] = newGen;
  }

  generateRandomGenom(length = 32) {
    this.genom = [];
    for (let i = 0; i < length; i++) {
      this.genom.push(Math.floor(Math.random() * 14));
    }
  }

  // Методы для проверки жизнеспособности
  checkIsAlive() {
    if ((this.energy[0] <= 0) || (this.minerals[0] <= 0)) {
      this.flagAlive = 0;
      this.color = 'gray';
    }
    if (this.age[0] >= this.age[1]) {
      this.flagAlive = 0;
    }
  }

  // Методы для геномной виртуальной машины
  isRelative(otherGenom) {
    const MAX_DIFF = 2;
    let diff = 0;
    
    if (this.genom.length !== otherGenom.length) return false;
    
    for (let i = 0; i < this.genom.length; i++) {
      if (this.genom[i] !== otherGenom[i]) {
        diff++;
        if (diff > MAX_DIFF) return false;
      }
    }
    return true;
  }

  // Методы для сброса флагов
  clearMoveParams() {
    this.flagMoved = 0;
  }
}

module.exports = Bot;