const Entity = require('./Entity');

class Mineral extends Entity {
  constructor(x, y) {
    super(x, y);
    this.objType = 'mineral';
    this.age = [0, 10];
    this.energy = [0, 128];
    this.minerals = [0, 2048];
    this.color = 'gray';
  }

  checkIsAlive() {
    if (this.age[0] >= this.age[1]) {
      this.flagAlive = 0;
    }
  }
}

module.exports = Mineral;