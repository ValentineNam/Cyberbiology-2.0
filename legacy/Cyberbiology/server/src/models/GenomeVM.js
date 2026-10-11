const { getRandomInt } = require('../utils/helpers');

class GenomeVM {
  constructor(bot) {
    this.bot = bot;
    this.instructionPointer = 0;
    this.memory = null;
    this.maxInstructions = 16;
    this.GENOM_LENGTH = 32;
  }

  execute() {
    let instructionsExecuted = 0;
    while (instructionsExecuted < this.maxInstructions && !this.bot.flagMoved) {
      const instruction = this.bot.genom[this.instructionPointer];
      this.executeInstruction(instruction);
      this.instructionPointer = (this.instructionPointer + 1) % this.bot.genom.length;
      instructionsExecuted++;
    }
  }

  executeInstruction(opcode) {
    switch(opcode) {
      case 0: this.mutate(); break;
      case 1: this.move(); break;
      case 2: this.turnRandom(); break;
      case 3: this.turnBasedOnNext(); break;
      case 4: this.turnFromMemory(); break;
      case 5: this.eat(); break;
      case 6: this.photosynthesis(); break;
      case 7: this.chemosynthesis(); break;
      case 8: this.mineralisation(); break;
      case 9: this.checkFront(); break;
      case 10: this.checkHunger(); break;
      case 11: this.checkAttacked(); break;
      case 12: this.checkAttackedAndJump(); break;
      case 13: this.longAge(); break;
      case 14: this.randomJump(); break;
      default: this.noOp(); break;
    }
  }

  // Реализация инструкций
  mutate() {
    this.bot.mutate();
    this.decreaseEnergy(1);
  }

  move() {
    // Логика перемещения будет реализована в WorldUpdater
    this.bot.flagMoved = 1;
  }

  turnRandom() {
    this.bot.direction = getRandomInt(1, 8);
    this.decreaseEnergy(1);
  }

  turnBasedOnNext() {
    const nextValue = this.bot.genom[(this.instructionPointer + 1) % this.GENOM_LENGTH];
    const spin = nextValue % 2 === 0 ? 'right' : 'left';
    this.turnDirection(spin);
    this.decreaseEnergy(1);
  }

  turnDirection(spin) {
    if (this.bot.direction !== 0) {
      if (spin === 'left') {
        this.bot.direction = this.bot.direction === 1 ? 8 : this.bot.direction - 1;
      } else if (spin === 'right') {
        this.bot.direction = this.bot.direction === 8 ? 1 : this.bot.direction + 1;
      }
    }
  }

  turnFromMemory() {
    if (this.memory !== null && this.memory > 0) {
      for (let i = 0; i < this.memory && i < this.maxInstructions; i++) {
        this.turnDirection('right');
      }
    } else {
      this.turnRandom();
    }
    this.memory = null;
  }

  eat() {
    // Логика поедания будет реализована в WorldUpdater
  }

  photosynthesis() {
    // Логика фотосинтеза будет реализована в WorldUpdater
  }

  chemoSynthesis() {
    if ((this.bot.minerals[0] > 9) && ((this.bot.energy[1] - this.bot.energy[0]) >= 32)) {
      this.bot.minerals[0] -= 8;
      this.bot.energy[0] += 32;
    }
  }

  mineralisation() {
    if ((this.bot.energy[0] > 40) && ((this.bot.minerals[1] - this.bot.minerals[0]) >= 8)) {
      this.bot.minerals[0] += 8;
      this.bot.energy[0] -= 32;
    }
  }

  checkFront() {
    // Логика проверки будет реализована в WorldUpdater
  }

  checkHunger() {
    // Логика проверки будет реализована в WorldUpdater
  }

  checkAttacked() {
    this.memory = this.getLastAttackedDirection();
  }

  checkAttackedAndJump() {
    // Логика проверки будет реализована в WorldUpdater
  }

  longAge() {
    const cost = 16;
    if (this.bot.energy[0] > cost) {
      this.bot.age[1] += 2;
      this.decreaseEnergy(cost);
    }
  }

  randomJump() {
    const nextValue = this.bot.genom[(this.instructionPointer + 1) % this.GENOM_LENGTH];
    const jumpOffset = getRandomInt(1, nextValue);
    this.instructionPointer = (this.instructionPointer + jumpOffset) % this.GENOM_LENGTH;
  }

  noOp() {
    // Пустая операция
  }

  decreaseEnergy(amount) {
    if (this.bot.energy[0] >= amount) {
      this.bot.energy[0] -= amount;
    } else {
      this.bot.checkIsAlive();
    }
  }

  getLastAttackedDirection() {
    if (this.bot.flagAttacked[0] > 0) {
      return this.bot.flagAttacked[0];
    } else if (this.bot.flagAttacked[1] > 0) {
      return this.bot.flagAttacked[1];
    }
    return null;
  }
}

module.exports = GenomeVM;