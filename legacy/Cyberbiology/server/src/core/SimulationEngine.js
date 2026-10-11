const World = require('../models/World');
const Bot = require('../models/Bot');
const Plant = require('../models/Plant');
const Mineral = require('../models/Mineral');
const GenomeVM = require('../models/GenomeVM');
const { getRandomInt } = require('../utils/helpers');

class SimulationEngine {
  constructor(width = 52, height = 52) { // 781/15 = 52
    this.world = new World(width, height);
    this.running = false;
    this.tickInterval = null;
    this.tickRate = 200; // ms
    this.maxSteps = 6400;
    this.GENS = 14;
    this.MUTATION_FACTOR = 15;
    this.TREE_GROWTH_SPEED = 2;
  }

  start() {
    this.running = true;
    this.tickInterval = setInterval(() => {
      this.tick();
    }, this.tickRate);
  }

  stop() {
    this.running = false;
    if (this.tickInterval) {
      clearInterval(this.tickInterval);
      this.tickInterval = null;
    }
  }

  tick() {
    if (!this.running) return;

    this.updateWorld();
    this.world.worldTime++;

    if (this.world.worldTime >= this.maxSteps) {
      this.stop();
    }
  }

  updateWorld() {
    // Обновляем всех существ в мире
    for (let x = 0; x < this.world.width; x++) {
      for (let y = 0; y < this.world.height; y++) {
        const entity = this.world.getEntity(x, y);
        if (entity) {
          if (entity.objType === 'bot') {
            this.updateBot(entity);
          } else if (entity.objType === 'plant') {
            this.updatePlant(entity);
          } else if (entity.objType === 'mineral') {
            this.updateMineral(entity);
          }
        }
      }
    }

    // Сбрасываем флаги атаки для всех ботов
    this.resetAttackFlags();
  }

  updateBot(bot) {
    // Запускаем виртуальную машину генома
    const vm = new GenomeVM(bot);
    vm.execute();

    // Проверяем потомство
    this.checkMakeChild(bot);

    // Обработка сна
    this.handleSleeping(bot);

    // Увеличение возраста
    if (bot.age[0] < bot.age[1]) {
      bot.age[0]++;
    }

    // Проверка на жизнь
    bot.checkIsAlive();

    // Если умер - превращаем в минерал
    if (bot.flagAlive === 0) {
      this.becomeMineral(bot);
    }

    // Сбрасываем флаг движения
    bot.flagMoved = 0;
  }

  updatePlant(plant) {
    // Рост растения
    this.growPlant(plant);

    // Проверка потомства
    this.checkPlantReproduction(plant);

    // Увеличение возраста
    if (plant.age[0] < plant.age[1]) {
      plant.age[0]++;
    }

    // Проверка на жизнь
    plant.checkIsAlive();

    // Если умер - превращаем в минерал
    if (plant.flagAlive === 0) {
      this.becomeMineral(plant);
    }
  }

  updateMineral(mineral) {
    // Увеличение возраста
    if (mineral.age[0] < mineral.age[1]) {
      mineral.age[0]++;
    }

    // Проверка на жизнь
    mineral.checkIsAlive();

    // Если достиг предельного возраста - исчезает
    if (mineral.flagAlive === 0) {
      this.world.removeEntity(mineral.x, mineral.y);
      this.world.worldEnergy += mineral.energy[0] + mineral.minerals[0] * 4;
    }
  }

  growPlant(plant) {
    let growthSpeed = 1;
    switch (plant.genus) {
      case 'tree': growthSpeed = 2 + this.TREE_GROWTH_SPEED; break;
      case 'bush': growthSpeed = 4 + this.TREE_GROWTH_SPEED; break;
      case 'grass': growthSpeed = 8 + this.TREE_GROWTH_SPEED; break;
    }

    const availableEnergy = this.world.worldEnergy - growthSpeed * 5;

    if (availableEnergy >= 0) {
      // Рост энергии
      if (plant.energy[0] < plant.energy[1]) {
        const energyToAdd = Math.min(growthSpeed, plant.energy[1] - plant.energy[0]);
        plant.energy[0] += energyToAdd;
        this.world.worldEnergy -= energyToAdd;
      }

      // Рост минералов
      if (plant.minerals[0] < plant.minerals[1]) {
        const mineralsToAdd = Math.min(growthSpeed, plant.minerals[1] - plant.minerals[0]);
        plant.minerals[0] += mineralsToAdd;
        this.world.worldEnergy -= mineralsToAdd * 4;
      }
    } else {
      const reducedGrowth = Math.floor(availableEnergy / 5);
      if (reducedGrowth > 0) {
        // Рост энергии
        if (plant.energy[0] < plant.energy[1]) {
          const energyToAdd = Math.min(reducedGrowth, plant.energy[1] - plant.energy[0]);
          plant.energy[0] += energyToAdd;
          this.world.worldEnergy -= energyToAdd;
        }

        // Рост минералов
        if (plant.minerals[0] < plant.minerals[1]) {
          const mineralsToAdd = Math.min(reducedGrowth, plant.minerals[1] - plant.minerals[0]);
          plant.minerals[0] += mineralsToAdd;
          this.world.worldEnergy -= mineralsToAdd * 4;
        }
      }
    }
  }

  checkMakeChild(bot) {
    const age = bot.age[0];
    const e = bot.getEnergyLevel();
    const m = bot.getMineralsLevel();

    if ((e >= 8) && (m >= 2) && (age >= 30)) {
      this.createBotChild(bot);
    }
  }

  createBotChild(parent) {
    // Пытаемся найти свободное место рядом
    for (let attempts = 0; attempts < 15; attempts++) {
      const dx = getRandomInt(-1, 1);
      const dy = getRandomInt(-1, 1);

      if (dx === 0 && dy === 0) continue;

      const newX = parent.x + dx;
      const newY = parent.y + dy;

      if (newX > 0 && newX < this.world.width - 1 && 
          newY > 0 && newY < this.world.height - 1 &&
          this.world.isEmpty(newX, newY)) {

        const childEnergy = Math.round(parent.energy[0] / 2);
        const childMinerals = Math.round(parent.minerals[0] / 2);

        const child = new Bot(newX, newY, parent.color);
        child.energy[0] = childEnergy;
        child.minerals[0] = childMinerals;
        child.genom = [...parent.genom]; // копируем геном

        // Мутация при рождении
        if (getRandomInt(1, 100) <= this.MUTATION_FACTOR) {
          child.mutate();
        }

        this.world.setEntity(newX, newY, child);

        // Обновляем родителя
        parent.energy[0] -= childEnergy;
        parent.minerals[0] -= childMinerals;

        break;
      }
    }
  }

  checkPlantReproduction(plant) {
    const age = plant.age[0];
    const e = plant.getEnergyLevel();
    const m = plant.getMineralsLevel();

    if ((e >= 7) && (m >= 7) && (age >= 30) && (getRandomInt(1, 100) <= 20)) {
      this.createPlantChild(plant);
    }
  }

  createPlantChild(parent) {
    const genusTypes = ['grass', 'bush', 'tree'];
    const d = genusTypes.indexOf(parent.genus) + 2; // d = 2, 3, 4

    for (let attempts = 0; attempts < 15; attempts++) {
      const dx = getRandomInt(-d, d);
      const dy = getRandomInt(-d, d);

      if (dx === 0 && dy === 0) continue;

      const newX = parent.x + dx;
      const newY = parent.y + dy;

      if (newX > 0 && newX < this.world.width - 1 && 
          newY > 0 && newY < this.world.height - 1 &&
          this.world.isEmpty(newX, newY)) {

        const childEnergy = Math.round(parent.energy[0] / 2);
        const childMinerals = Math.round(parent.minerals[0] / 2);

        const child = new Plant(newX, newY, parent.genus);
        child.energy[0] = childEnergy;
        child.minerals[0] = childMinerals;

        this.world.setEntity(newX, newY, child);

        // Обновляем родителя
        parent.energy[0] -= childEnergy;
        parent.minerals[0] -= childMinerals;

        break;
      }
    }
  }

  handleSleeping(bot) {
    if (bot.flagSleeping !== 0) {
      bot.flagSleeping++;
    }

    if (bot.flagSleeping >= 10) {
      this.decreaseEnergy(bot, 1);
      bot.flagSleeping = 1;
    }
  }

  becomeMineral(entity) {
    const e = entity.energy[0];
    const m = entity.minerals[0];

    if (e > 0 || m > 0) {
      const mineral = new Mineral(entity.x, entity.y);
      mineral.energy[0] = e;
      mineral.minerals[0] = m;

      this.world.setEntity(entity.x, entity.y, mineral);
      
      // Ограничиваем параметры минерала
      if (mineral.energy[0] > mineral.energy[1]) {
        this.world.worldEnergy += (mineral.energy[0] - mineral.energy[1]);
        mineral.energy[0] = mineral.energy[1];
      }
      if (mineral.minerals[0] > mineral.minerals[1]) {
        this.world.worldEnergy += 4 * (mineral.minerals[0] - mineral.minerals[1]);
        mineral.minerals[0] = mineral.minerals[1];
      }
    } else {
      this.world.removeEntity(entity.x, entity.y);
      this.world.worldEnergy += (e + m * 4);
    }
  }

  resetAttackFlags() {
    for (let x = 0; x < this.world.width; x++) {
      for (let y = 0; y < this.world.height; y++) {
        const entity = this.world.getEntity(x, y);
        if (entity && entity.objType === 'bot') {
          entity.flagAttacked.pop();
          entity.flagAttacked.unshift(0);
        }
      }
    }
  }

  decreaseEnergy(entity, amount) {
    if (entity.energy[0] >= amount) {
      entity.energy[0] -= amount;
      this.world.worldEnergy += amount;
    } else {
      entity.checkIsAlive();
    }
  }

  // Методы для управления симуляцией
  addBot(x, y, genom = null) {
    const bot = new Bot(x, y);
    if (genom) {
      bot.genom = genom;
    } else {
      bot.generateRandomGenom();
    }
    this.world.setEntity(x, y, bot);
    return bot;
  }

  addPlant(x, y, genus = 'tree') {
    const plant = new Plant(x, y, genus);
    this.world.setEntity(x, y, plant);
    return plant;
  }

  addMineral(x, y) {
    const mineral = new Mineral(x, y);
    this.world.setEntity(x, y, mineral);
    return mineral;
  }

  getWorldState() {
    return this.world.getWorldState();
  }
}

module.exports = SimulationEngine;