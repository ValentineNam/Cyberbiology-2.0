const Entity = require('./Entity');

class Plant extends Entity {
  constructor(x, y, genus = 'tree') {
    super(x, y);
    this.objType = 'plant';
    this.genus = genus; // 'tree', 'bush', 'grass'
    
    switch(genus) {
      case 'tree':
        this.age = [0, 512];
        this.energy = [0, 2048];
        this.minerals = [0, 2048];
        break;
      case 'bush':
        this.age = [0, 256];
        this.energy = [0, 1024];
        this.minerals = [0, 1024];
        break;
      case 'grass':
        this.age = [0, 64];
        this.energy = [0, 256];
        this.minerals = [0, 256];
        break;
    }
    
    this.color = 'green';
  }

  checkIsAlive() {
    if ((this.energy[0] <= 0) || (this.minerals[0] <= 0)) {
      this.flagAlive = 0;
      this.color = 'gray';
    }
    if (this.age[0] >= this.age[1]) {
      this.flagAlive = 0;
    }
  }
}

module.exports = Plant;