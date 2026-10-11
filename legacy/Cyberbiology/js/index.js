'use strict'

import { drawTree, drawBush, drawGrass, drawBot, drawMineral } from './draw_models.js';
// import { addListeners, setPause } from './utils.js';

// addListeners();

const
	CANVAS_WIDTH = 781,
	CANVAS_HEIGTH = 781,
	GRID_SIZE = 15,
	GENOM_LENGTH = 32,
	MUTATION_FACTOR = 15,
	GENS = 14, // количество разных генов
	STEPS = 6400,
	TREE_GROWTH_SPEED = 2,
	ENERGY_PER_CELL = 512;

let render_speed = 320,
	pause = 1,
	timerId,
	world_width = Math.floor(CANVAS_WIDTH / GRID_SIZE),
	world_heigth = Math.floor(CANVAS_HEIGTH / GRID_SIZE);

let worldTime = 0;
let worldEnergy = world_width * world_heigth * ENERGY_PER_CELL;
let fullWorldEnergy = 0;

let worldMatrix = create2DArray(world_width, world_heigth);

const canvas = document.querySelector('canvas');
const ctx = canvas.getContext('2d');

canvas.width = CANVAS_WIDTH;
canvas.height = CANVAS_HEIGTH;

/* Класс бот */
class Bot {
	constructor(x, y, color) {
		this.objType = 'bot';
		this.age = [0,128];
		this.x = x;
		this.y = y;
		this.color = color; // ! ToDo: цвет наследуется от предков и зависит от характера питания
		this.direction = 1;
		this.flagAttacked = [0,0]; // * позиция 0 - в текущем ходе, 1я - в предыдущем; 1-8 - направление, откуда атакаван или 0 - не атакован
		this.flagSleeping = 0; // * 1-10 спит, 0 не спит
		this.flagHungry = 0;
		this.flagMoved = 0;
		this.flagAlive = 1;
		this.energy = [0,1024];
		this.minerals = [0,256];
		this.speed = 10;
		this.genom = []; // * от этого генома зависит поведение бота, по сути этого его ментальная программа
		this.paramsGenom = []; // ! ToDo: сделать параметрический геном, от которого зависит - какие параметры какие значения будут иметь
		this.eatings = [0,0,0,0];   // * кушает 0 - растения, 1 - других ботов, 2 - мясо, 3 - минералы
	}
/* Метод генерации рандомного генома */
	generateRandomGenom() {
		this.genom = randomGenomGenerator();
	}
/* Метод мутации генома */
	mutate() {
		this.genom = genomMutate(this);
	}
/* Метод отрисовки бота на холсте */
	draw() {
		let s = GRID_SIZE / 10; // scale
		let x = this.x * 10,
				y = this.y * 10;
		drawBot(ctx, x, y, s, this.color);
	}
/* Метод увеличения возраста */
	incAge = incrementAge;
/* Метод перемещения в направлении взгляда */    
	move() {
		let moveSpeed = setMoveSpeed(this);
		checkEnergyForMove(this, moveSpeed) ? botMove(this, moveSpeed) : botSleep(this);
	}
/* Метод изменения направления взгляда */    
	changeDirection(opt) {
		this.direction = chooseNewDirection(this.direction, opt);
	}
/* Метод поедания объекта, находящегося спереди в направлении взгляда */   
	eat() {
		botEatFrontObject(this);
	}
/* Метод получения энергии из окружающего пространства */   
	getGreenEnergy() {
		photosynthesis(this);
	}
// /* Метод проверки, кто/что спереди по направлению взгляда */
// 	botCheckFrontDirection() {
// 		return changeAdrDependOfFrontObj(this);
// 	}
/* Метод проверки бота - жив ли он? */   
	isAlive() {
		checkIsAlive(this);
		if (this.flagAlive == 0) {
			becomeMineral(this);
		}
	}
/* метод конвертации минералов в энергию */
	chemosynthesis() {
		if ((this.minerals[0] > 9) && ((this.energy[1] - this.energy[0]) >= 32)) {
			this.minerals[0] -= 8;
			this.energy[0] += 32;
		}
	}
/* метод конвертации энергии в минералы */
	mineralisation() {
		if ((this.energy[0] > 40) && ((this.minerals[1] - this.minerals[0]) >= 8)) {
			this.minerals[0] += 8;
			this.energy[0] -= 32;
		}
	}
/* Метод обработки сна */
	isSleeping() {
		sleepingMechanics(this);
	}
/* Метод проверки возможности создания нового бота */    
	checkMakeChild = botCheckMakeChild;
/* Метод создания нового бота */     
	createChild = botMakeChild;
/* Метод переводит флаг движения в состояние 0 */
	clearMoveParams() {
		this.flagMoved = 0;
	}
/* Увеличение максимального возраста */
	longAge() {
		let cost = 16;
		if (this.energy[0] > cost) {
			this.age[1] += 2;
			botDecEnergy(this, cost);
		}
	}
}

function setMoveSpeed(botObj) {
	let eLvl = checkOwnParamLvl(botObj, 'energy'),
			mLvl = checkOwnParamLvl(botObj, 'minerals');
	return (botObj.direction % 2 == 1) ?
		10 - eLvl +  Math.ceil(mLvl / 2) :
		Math.ceil(1.41 * (10 - eLvl +  (mLvl / 2)));   // * шаг по диагонали требует в 1.41 раз больше энергии
}

function botMove(botObj, moveSpeed) {
	let ax = botObj.x,
		ay = botObj.y,
		frontCoords = getFrontCellCoordinates(botObj.direction, ax, ay);
	if ((frontCoords != -1) && (botObj.flagMoved != 1)) {
		let bx = frontCoords[0],
			by = frontCoords[1];
		let frontObj = botCheckDirection(botObj, bx, by);
		if (frontObj == 0) {
			worldMatrix[bx][by] = botObj;
			worldMatrix[bx][by].x = bx;
			worldMatrix[bx][by].y = by;
			worldMatrix[ax][ay] = new Space();
			botDecEnergy(botObj, moveSpeed);
			botObj.flagMoved = 1;
		}
	}
}

function botEatFrontObject(botObj) {
	let ax = botObj.x,
		ay = botObj.y,
		frontCoords = getFrontCellCoordinates(botObj.direction, ax, ay);
	if ((frontCoords != -1) && (botObj.flagMoved != 1)) {
		let bx = frontCoords[0],
			by = frontCoords[1];
		let frontObjType = botCheckDirection(botObj, bx, by);
		// * если пусто = 0, родственник = 1, чужой бот = 2, мясо = 3, дерево = 4, минерал = 5, стена = -1, ошибка 255
		switch (frontObjType) {
			// * группируем кейсы 1-5
			case 1:
			case 2:
			case 3:
			case 4:
			case 5:
				eatFromCoords(botObj, bx, by);
				break;
		
			default:
				break;
		}
	}
}

function eatFromCoords(botObj, x, y) {
	let frontObj = worldMatrix[x][y],
		frontType = frontObj.objType,
		energyLvl = checkOwnParamLvl(botObj, 'energy'),
		multiplier = 1;
	if (energyLvl <= 2) {
		botObj.flagHungry = 1;
	}
	if (botObj.flagHungry == 1) {
		multiplier = 2.5;
	}
	switch (frontType) {
		case 'bot':
			botEatBot(botObj, frontObj, multiplier);
			break;
		case 'tree':
			botEatTree(botObj, frontObj, multiplier);
			break;
		case 'mineral':
			botEatMineral(botObj, frontObj, multiplier);
			break;
		default:
			break;
	}
	botDecEnergy(botObj, 1);
}

// ! ToDo: Дописать эту функцию - случай, когда бот не смог победить
function botEatBot(botObj, frontObj, multiplier) {
	let aMinerals = botObj.minerals[0],
			bMinerals = frontObj.minerals[0],
			chanceToWin = getRandomInt(1, 100);
	if (bMinerals > aMinerals) { // * если атакуемый бот "толще" по минералам
		chanceToWin > 0 ?
			botWin(botObj, frontObj, multiplier) : // * откусили (20% шанс)
			false ; // * не откусили (80% шанс) потратили свою энергию, потратили свои минералы и уменьшили минералы атакуемого
	} else {
		chanceToWin > 0 ?
			botWin(botObj, frontObj, multiplier) : // * откусили (80% шанс)
			false ; // * не откусили (20% шанс)
	}
}

/* Функция победы в бою - бот откусывает часть энергии и минералов */
function botWin(botObj, frontObj, multiplier = 1) {
	let aEnergy = botObj.energy[0],
		aMinerals = botObj.minerals[0],
		bEnergy = frontObj.energy[0],
		bMinerals = frontObj.minerals[0],
		oneBite = 80;
	multiplier * oneBite >= bEnergy ? oneBite = bEnergy : oneBite *= multiplier ; // * не можем съесть больше, чем у бота есть энергии
	oneBite + aEnergy > botObj.energy[1] ? oneBite = botObj.energy[1] - aEnergy : false ; // * не можем съесть больше, чем вмещается
	botObj.energy[0] += oneBite;
	frontObj.energy[0] -= oneBite;
	Math.ceil(oneBite / 5) >= bMinerals ? oneBite = bMinerals : oneBite = Math.ceil(oneBite / 5) ; // * бот отъедает от другого бота в 5 раз меньше минералов, чем энергии 
	oneBite + aMinerals > botObj.minerals[1] ? oneBite = botObj.minerals[1] - aMinerals : false ;
	botObj.minerals[0] += oneBite;
	frontObj.minerals[0] -= oneBite;
	checkIsAlive(frontObj);
	// ! ToDo: переписать на наследование цвета, в зависимости от питания предков
	botObj.color = colors[1][0]; // * бот краснеет, если питается мясом
}

function checkIsAlive(obj) {
	if ((obj.objType == 'bot') || (obj.objType == 'tree')) {
		if ((obj.energy[0] <= 0) || (obj.minerals[0] <= 0)) { // * бот не может жить, если у него нет энергии или минералов ака костей
			obj.flagAlive = 0;
			obj.color = 'gray';
		}
	}
	obj.age[0] >= obj.age[1] ? obj.flagAlive = 0 : false ; // * если дожили до "предельного" возраста, то умираем
}

/* Если бот спит на протяжении 10 ходов подряд - он теряет 1 ед энергии */
function sleepingMechanics(botObj) {
	botObj.flagSleeping != 0 ? botObj.flagSleeping += 1 : false ;
	if (botObj.flagSleeping >= 10) {
		botDecEnergy(botObj, 1);
		botObj.flagSleeping = 1;
	} 
}

function incParam(param, increment = 1) {
	return increment >= 0 ? param += increment : ++param ;
}

function botEatTree(botObj, frontObj, multiplier) {
	let aEnergy = botObj.energy[0],
		aMinerals = botObj.minerals[0],
		bEnergy = frontObj.energy[0],
		bMinerals = frontObj.minerals[0],
		oneBite = 120;
	multiplier * oneBite >= bEnergy ? oneBite = bEnergy : oneBite *= multiplier ; // * не можем съесть больше, чем у бота есть энергии
	oneBite + aEnergy > botObj.energy[1] ? oneBite = botObj.energy[1] - aEnergy : false ; // * не можем съесть больше, чем вмещается
	botObj.energy[0] += oneBite;
	frontObj.energy[0] -= oneBite;
	Math.ceil(oneBite / 4) >= bMinerals ? oneBite = bMinerals : oneBite = Math.ceil(oneBite / 4) ; // * бот отъедает от дерева в 4 раз меньше минералов, чем энергии 
	oneBite + aMinerals > botObj.minerals[1] ? oneBite = botObj.minerals[1] - aMinerals : false ;
	botObj.minerals[0] += oneBite;
	frontObj.minerals[0] -= oneBite;
	checkIsAlive(frontObj);
	// ! ToDo: переписать на наследование цвета, в зависимости от питания предков
	botObj.color = colors[6][0]; // * бот зеленеет, если питается зеленью
}

function botEatMineral(params) {
	
}

function botSleep(botObj) {
	botObj.direction = 0;
	botObj.flagSleeping = 1;
}

function botDecEnergy(botObj, decrement) {
	if (botObj.energy[0] >= decrement) {
		botObj.energy[0] -= decrement;
		worldEnergy += decrement;
	} else {
		checkIsAlive(botObj);
	}
}

/* Фотосинтез - получение энергии из окружающего пространства */
function photosynthesis(obj, increment = 14) {
	if ((obj.energy[1]-obj.energy[0]) <= increment) {
		increment = obj.energy[1]-obj.energy[0];
	}
	if (worldEnergy >= increment) {
		// incParam(obj.energy[0], increment); //  Странно, но в этом варианте энергия утекает вникуда...
		obj.energy[0] += increment;
		worldEnergy -= increment;
	} else if (worldEnergy > 0) {
		// incParam(obj.energy[0], worldEnergy);
		obj.energy[0] += worldEnergy;
		worldEnergy = 0;
	}
}

/* Меняем направление взгляда бота - возвращает новое значение direction в зависимости от условий */
function chooseNewDirection(dir, opt = 'random') {
	let newDirection;
	switch (opt) {
		case 'random':
			newDirection = getRandomInt(1, 8);
			break;
		case 'left':
			newDirection = botChangeDirection(dir, 'left');
		break;
		case 'right':
			newDirection = botChangeDirection(dir, 'right');
			break;
		case 'sleep':
			newDirection = 0;
			break;
		default:
			break;
	}
	return newDirection;
}

/* Бот поворачивается на 1 сектор в направлении spin, относительно текущего направления */
function botChangeDirection(...[direction, spin]) {
	if (direction != 0) {
		switch (spin) {
			case 'left':
				if (direction != 1) {
					direction--;
				} else {
					direction = 8;
				}
				break;
			case 'right':
				if (direction != 8) {
					direction++;
				} else {
					direction = 1;
				}
				break;
			default:
				direction = getRandomInt(1, 8);
		}
	} else {
		direction = getRandomInt(1, 8);
	}
	return direction;
}

/* Вычисление координат клетки в направлении взгляда бота */
// Прости меня будущий я, но как это сделать иначе мне не понятно 18.11.20
function getFrontCellCoordinates(viewDirection = 0, botPosX, botPosY) {
	let coordsXY = -1;
	if (viewDirection != 0) {
		switch (viewDirection) {
			case 1:
				if (botPosY != 0) {
					coordsXY = [botPosX, botPosY - 1];	
				} else {
					return -1;
				}
				break;
			case 2:
				if (botPosX < world_width - 1 && botPosY != 0) {
					coordsXY = [botPosX + 1, botPosY - 1];	
				} else {
					return -1;
				}
				break;
			case 3:
				if (botPosX < world_width- 1) {
					coordsXY = [botPosX + 1, botPosY];	
				} else {
					return -1;
				}
				break;
			case 4:
			if (botPosX < world_width- 1 && botPosY < world_heigth - 1) {
				coordsXY = [botPosX + 1, botPosY + 1];	
			} else {
				return -1;
			}
			break;
			case 5:
			if (botPosY < world_heigth- 1) {
				coordsXY = [botPosX, botPosY + 1];	
			} else {
				return -1;
			}
			case 6:
			if (botPosX > 0 && botPosY < world_heigth- 1) {
				coordsXY = [botPosX - 1, botPosY + 1];	
			} else {
				return -1;
			}
			break;
			case 7:
			if (botPosX > 0) {
				coordsXY = [botPosX - 1, botPosY];	
			} else {
				return -1;
			}
			break;
			case 8:
			if (botPosX > 0 && botPosY > 0) {
				coordsXY = [botPosX - 1, botPosY - 1];	
			} else {
				return -1;
			}
			break;

			default:
				return -1;
				// break;
		}
	} else if (viewDirection == 0) {
		coordsXY = -1;
	}
	return coordsXY; //[x,y] || -1
}

/* Функция проверки объекта в указанных координатах */
function botCheckDirection(botObj, x, y) { // * получаем координаты, возвращаем ответ 
	// * если пусто = 0, родственник = 1, чужой бот = 2, мясо = 3, дерево = 4, минерал = 5, стена = -1, ошибка 255
	let objType = worldMatrix[x][y].objType;
	let res;
	switch (objType) {
		case 'space':
			res = 0;
			break;
		case 'bot':
			let frontBot = worldMatrix[x][y];
			isRelative(botObj.genom, frontBot.genom) == 1 ? 
				isRelative(botObj.paramsGenom, frontBot.paramsGenom) == 1 ? res = 1 : res = 2 :
			res = 2;
		case 'meat':
			res = 3;
			break;
		case 'tree':
			res = 4;
			break;
		case 'mineral':
			res = 5;
			break;
		case 'wall':
			res = -1;
			break;
		default:
			res = 255;
			break;
	}
	return res;
}

/* Бот проверяет достаточно ли ему энергии, чтобы двигаться? */
function checkEnergyForMove(botObj, moveCost) {
	if (moveCost != undefined) {
		let e = botObj['energy'][0];
		return e > moveCost ? true : false;
	} else {
		return false;
	}
}

/* Проверяем количество различий между геномами ботов (проверка на родственность) */
function isRelative(a, b) { // передаем геномы ботов
	let res = -1;
	const MAX_DIFF = 2; // Максимальное отличие, чтобы считаться родственником
	let diff = 0;
	if (a.length == b.length) {
		for (let i = 0; i < a.length; i++) {
			if (a[i] != b[i]) {
				diff++;
			}
			if (diff > MAX_DIFF) {
				res = 0;
				break;
			}
		}
		if (diff <= MAX_DIFF) {
			res = 1;
		}
	}
	return res; // -1 разного размера геномы, 0 не родственники, 1 родственники
}

/* Функция создания потомка в случайной области заданного радиуса */
function botMakeChild() {
	let parentX = this.x,
		parentY = this.y,
		newX,
		newY,
		parentGenom = this.genom;
// * пробуем найти место рядом с собой, чтобы отпочковать нового бота
	for (let index = 15; index--; ) {
		let dx = getRandomInt(-1, 1),
			dy = getRandomInt(-1, 1);
		
		while ((dx == 0) && (dy == 0)) {
			dx = getRandomInt(-1, 1),
			dy = getRandomInt(-1, 1);
		}
	
		newX = parentX + dx;
		newY = parentY + dy;
	
		if ((newX > 0 && newX < world_width - 1) && (newY > 0 && newY < world_heigth - 1)) {
			if (worldMatrix[newX][newY].objType == 'space') {
				let temp = Math.round(worldMatrix[parentX][parentY].energy[0] / 2);
// ! ToDo: дописать функцию определения цвета, в зависимости от питания и передавать этот цвет в конструктор нового бота
// ! ToDo: по-мимо цвета, нужно передавать еще геномы новым ботам с шансом мутации одного из параметров
				worldMatrix[newX][newY] = new Bot(newX, newY, colors[5][0]);
				worldMatrix[newX][newY].energy[0] = temp;
				worldMatrix[parentX][parentY].energy[0] = worldMatrix[parentX][parentY].energy[0] - temp;
				temp = Math.round(worldMatrix[parentX][parentY].minerals[0] / 2);
				worldMatrix[newX][newY].minerals[0] = temp;
				worldMatrix[parentX][parentY].minerals[0] = worldMatrix[parentX][parentY].minerals[0] - temp;
				worldMatrix[newX][newY].genom = parentGenom;
				roll(MUTATION_FACTOR) ? worldMatrix[newX][newY].mutate() : false; // при рождении - у бота есть шанс мутировать 1 ген
				index = 0;
			} else {
				continue;
			}		
		}
	}
}

/* Функция проверки ботом, а не пора ли создать потомка? */
function botCheckMakeChild() {
	let age = this.age[0],
		e = checkOwnParamLvl(this, 'energy'),
		m = checkOwnParamLvl(this, 'minerals');
	if ((e >= 8) && (m >= 2) && (age >= 30)) {
		this.createChild();
	}
}

class Tree {
	constructor(x, y) {
		this.objType = 'tree';
		this.age = [0,512];
		this.x = x;
		this.y = y;
		this.energy = [0,2048];
		this.minerals = [0,2048];
		this.flagAlive = 1;
		this.genus = 'tree';
		this.color = colors[7][0];
	}

	draw() {
		let s = GRID_SIZE / 10; // scale
		let x = this.x * 10,
			y = this.y * 10;
		drawTree(ctx, x, y, s, this.color);
	}

	isAlive() {
		checkIsAlive(this);
		if (this.flagAlive == 0) {
			becomeMineral(this);
		}
	}
}
// ! ToDo: Найти и пофиксить баг утечкой энергии
function becomeMineral(obj) {
		// console.log(`ALIVE == 0`);
		// let obj = worldMatrix[obj.x][obj.y];
		let e = 1 * obj.energy[0],
				m = 1 * obj.minerals[0];
		if ((obj.energy[0] > 0) || (obj.minerals[0] > 0)) {
					worldMatrix[obj.x][obj.y] = new Mineral(obj.x, obj.y);
			// console.log(`CREATE MINERAL`);
			worldMatrix[obj.x][obj.y].energy[0] = e;
			worldMatrix[obj.x][obj.y].minerals[0] = m;
			if (worldMatrix[obj.x][obj.y].energy[0] > worldMatrix[obj.x][obj.y].energy[1]) {
				console.log(`e[0]=${worldMatrix[obj.x][obj.y].energy[0]}, e[1]=${worldMatrix[obj.x][obj.y].energy[1]}`);
				console.log(`we before =${worldEnergy}`);
				worldEnergy += (worldMatrix[obj.x][obj.y].energy[0] - worldMatrix[obj.x][obj.y].energy[1]);
				worldMatrix[obj.x][obj.y].energy[0] = 1 * worldMatrix[obj.x][obj.y].energy[1];
				console.log(`we after =${worldEnergy}`);
			}
			if (worldMatrix[obj.x][obj.y].minerals[0] > worldMatrix[obj.x][obj.y].minerals[1]) {
				worldEnergy += 4 * (worldMatrix[obj.x][obj.y].minerals[0] - worldMatrix[obj.x][obj.y].minerals[1]);
				worldMatrix[obj.x][obj.y].minerals[0] = 1 * worldMatrix[obj.x][obj.y].minerals[1];
			}
		} else {
			console.log(`ELSE ????`);
			worldMatrix[obj.x][obj.y] = new Space(obj.x, obj.y);
			worldEnergy += (e + m * 4);
		}
}

function annihilation(obj) {
	worldEnergy += (1 * worldMatrix[obj.x][obj.y].energy[0] + 4 * worldMatrix[obj.x][obj.y].minerals[0]);
	worldMatrix[obj.x][obj.y] = new Space(obj.x, obj.y);
}

class Bush {
	constructor(x, y) {
		this.objType = 'tree';
		this.age = [0,256];
		this.x = x;
		this.y = y;
		this.energy = [0,1024];
		this.minerals = [0,1024];
		this.flagAlive = 1;
		this.genus = 'bush';
		this.color = colors[7][0];
	}

	draw() {
		let s = GRID_SIZE / 10; // scale
		let x = this.x * 10,
			y = this.y * 10;
		drawBush(ctx, x, y, s, this.color);
	}

	isAlive() {
		checkIsAlive(this);
		if (this.flagAlive == 0) {
			becomeMineral(this);
		}
	}
}

class Grass {
	constructor(x, y) {
		this.objType = 'tree';
		this.age = [0,64];
		this.x = x;
		this.y = y;
		this.energy = [0,256];
		this.minerals = [0,256];
		this.flagAlive = 1;
		this.genus = 'grass';
		this.color = colors[7][0];
	}

	draw() {
		let s = GRID_SIZE / 10; // scale
		let x = this.x * 10,
				y = this.y * 10;
		drawGrass(ctx, x, y, s, this.color);
	}

	isAlive() {
		checkIsAlive(this);
		if (this.flagAlive == 0) {
			becomeMineral(this);
		}
	}
}

class TreeFactory {
	static list = {
		tree: Tree,
		bush: Bush,
		grass: Grass
	}

	create(x, y, type = 'tree') {
		const TreeType = TreeFactory.list[type] || TreeFactory.list.tree;
		const newTree = new TreeType(x, y);
		newTree.growth = treeGrowth;
		newTree.incAge = incrementAge;
		newTree.createChild = treeMakeChild;
		newTree.checkMakeChild = treeCheckMakeChild;
		return newTree;
	}
}

/* Функция роста дерева */
function treeGrowth() {
	let e, m;
	let growthSpeed = 1,
		newGrowthSpeed = 0;
	switch (this.genus) {
		/* Tree genus */
		case 'tree':
			growthSpeed = 2 + TREE_GROWTH_SPEED;
			break;
		/* Bush genus */
		case 'bush':
			growthSpeed = 4 + TREE_GROWTH_SPEED;
			break;
		/* Bush grass */
		case 'grass':
			growthSpeed = 8 + TREE_GROWTH_SPEED;
			break;
		default:
			break;
	}
	let x = this.x, 
		y = this.y;
	// ! ToDo: Этот кусок можно явно переписать как-то красивее
	e = worldMatrix[x][y].energy;
	m = worldMatrix[x][y].minerals;
	if ((worldEnergy - growthSpeed * 5) >= 0) {
		if (e[0] < e[1]) {
			if ((e[0] + growthSpeed) <= e[1]) {
				e[0] += growthSpeed;
				worldEnergy -= growthSpeed;
			} else {
				newGrowthSpeed = e[1] - e[0];
				e[0] += newGrowthSpeed;
				worldEnergy -= newGrowthSpeed;
			}
		}
		if (m[0] < m[1]) {
			if ((m[0] + growthSpeed) <= m[1]) {
				m[0] += growthSpeed;
				worldEnergy -= (growthSpeed * 4);
			} else {
				newGrowthSpeed = m[1] - m[0];
				m[0] += newGrowthSpeed;
				worldEnergy -= (newGrowthSpeed * 4);
			}
		}
	} else {
		newGrowthSpeed = Math.floor(worldEnergy / 5);
		if (e[0] < e[1]) {
			if ((e[0] + newGrowthSpeed) <= e[1]) {
				e[0] += newGrowthSpeed;
				worldEnergy -= newGrowthSpeed;
			} else {
				newGrowthSpeed = e[1] - e[0];
				e[0] += newGrowthSpeed;
				worldEnergy -= newGrowthSpeed;
			}
		}
		if (m[0] < m[1]) {
			if ((m[0] + newGrowthSpeed) <= m[1]) {
				m[0] += newGrowthSpeed;
				worldEnergy -= (newGrowthSpeed * 4);
			} else {
				newGrowthSpeed = m[1] - m[0];
				m[0] += newGrowthSpeed;
				worldEnergy -= (newGrowthSpeed * 4);
			}
		}
	}
}

/* Функция создания потомка дерева в случайной области заданного радиуса */
function treeMakeChild() {
	let parentX = this.x,
		parentY = this.y,
		newX,
		newY;
	let genusTypes = ['grass', 'bush', 'tree'];
	let d = genusTypes.indexOf(this.genus) + 2; // d = 2, 3, 4
	for (let index = 15; index--; ) {
		let dx = getRandomInt(-d, d),
				dy = getRandomInt(-d, d);
		
		while ((dx == 0) && (dy == 0)) {
			dx = getRandomInt(-d, d),
			dy = getRandomInt(-d, d);
		}
	
		newX = parentX + dx;
		newY = parentY + dy;
	
		if ((newX > 0 && newX < world_width - 1) && (newY > 0 && newY < world_heigth - 1)) {
			if (worldMatrix[newX][newY].objType == 'space') {
				let temp = Math.round(worldMatrix[parentX][parentY].energy[0] / 2);
				worldMatrix[newX][newY] = treeFactory.create(newX, newY, this.genus);
				worldMatrix[newX][newY].energy[0] = temp;
				worldMatrix[parentX][parentY].energy[0] = worldMatrix[parentX][parentY].energy[0] - temp;
				temp = Math.round(worldMatrix[parentX][parentY].minerals[0] / 2);
				worldMatrix[newX][newY].minerals[0] = temp;
				worldMatrix[parentX][parentY].minerals[0] = worldMatrix[parentX][parentY].minerals[0] - temp;
				index = 0;
			} else {
				continue;
			}		
		}
	}
}

/* Функция проверки деревом, а не пора ли создать потомка? */
function treeCheckMakeChild() {
	let age = this.age[0],
		e = checkOwnParamLvl(this, 'energy'),
		m = checkOwnParamLvl(this, 'minerals');
	if ((e >= 7) && (m >= 7) && (age >= 30)) {
		// размножается с шансом 20%
		// if (roll(20)) {
		// 	this.createChild(); 
		// 	console.log(`rolled`);
		// } else {
		// 	console.log(`not rolled`);
		// }
		(roll(20)) ? this.createChild() : false;
	}
}

/* Объект проверяет свой уровень энергии или другого параметра */
function checkOwnParamLvl(obj, paramType = 'energy') {
	if (paramType != undefined) {
		let param = obj[paramType][0],
				maxParam = obj[paramType][1],
				paramLvl = Math.floor(param / maxParam * 10);
		return paramLvl; // возвращаем уровень от 0 - 10
	} else {
		return false;
	}
}

/* Увеличиваем возраст объекта */
function incrementAge() {
	if (this.age[0] < this.age[1]) {
		this.age[0]++;
	}
}

function roll(percent) {
	let isRolled;
	return  isRolled = (percent >= getRandomInt(1, 100));
}

class Space {
	constructor(x, y) {
		this.objType = 'space';
	}
}

class Mineral {
	constructor(x, y) {
		this.objType = 'mineral';
		this.age = [0,10];
		this.x = x;
		this.y = y;
		this.energy = [0,128];
		this.minerals = [0,2048];
		this.flagAlive = 1;
		this.color = 'gray';
	}
	draw() {
		let s = GRID_SIZE / 10; // scale
		let x = this.x * 10,
			y = this.y * 10;
		drawMineral(ctx, x, y, s, this.color);
	}
/* Метод увеличения возраста */
	incAge = incrementAge;
/* По достижению определенного возраста минералы превращаются в энергию */
	isAlive() {
		checkIsAlive(this);
		if (this.flagAlive == 0) {
			annihilation(this);
		}
	}
}

class Wall {
	constructor(x, y) {
		this.objType = 'wall';
	}
}

/* Заполняем "мир" пустым пространством */
function emptySpaceGenerator(worldObj) {
	for(let j = worldObj.length; j--;) {
		for(let i = worldObj[j].length; i--;) {
			worldObj[j][i] = new Space();
		}
	}
}

/* Возвращает геном (массив длиной 16 из случайных чисел от 0 до GENS) */
function randomGenomGenerator(genomLength = GENOM_LENGTH, genomLowAdr = 0, genomHighAdr = GENS) {
	let GENOM = [];
	for (let x = genomLength; x--;) {
		GENOM.push(getRandomInt(genomLowAdr, genomHighAdr));
	};
	return GENOM;
}

/* возвращает случайное число в диапазоне [min, max] */
function getRandomInt(min, max) {
	if (min < max) {
		return Math.floor(Math.random() * (max - min + 1)) + min;
	} else {
		return Math.floor(Math.random() * (min - max + 1)) + max;
	}
}

/* создает 2-мерный массив размерностью (rows * columns) */
function create2DArray(rows = 5, columns = 5) {
	let arr = new Array(rows);
	for (let i = 0; i < arr.length; i++) {
		arr[i] = new Array(columns);
	}
	return arr;
}

/* Создаем стену по краю мира */
function buildTheWorldWall(arr) {
	for (let i = arr.length-1; i--;) {
		arr[0][i] = new Wall(); // top border
 		arr[i][arr[0].length-1] = new Wall(); // right border
		arr[arr.length-1][i+1] = new Wall(); // bottom border
		arr[i+1][0] = new Wall(); // left border
		
	}
}

addEventListener('click', (event) => {
	let rect = canvas.getBoundingClientRect();
	let x = event.clientX - rect.left,
		y = event.clientY - rect.top;
	if ((x > CANVAS_HEIGTH) ||
		(x < 0) ||
		(y > CANVAS_WIDTH) ||
		(y < 0)) {
		return ;
	};
	let tX = Math.floor(x / GRID_SIZE),
	  	tY = Math.floor(y / GRID_SIZE);
	let objType = worldMatrix[tX][tY].objType;
	let info = document.getElementById('info-output');
	info.value = `x: ${tX}, y: ${tY}\nObject: ${objType}`;
	objType == 'bot' ? info.value += `\nGenom:\n[${worldMatrix[tX][tY].genom}]` : false;
	(objType == 'bot' || objType == 'tree') ? info.value += `\nAge:\n[${worldMatrix[tX][tY].age}]` : false;
	(objType == 'bot' || objType == 'tree') ? info.value += `\nEnergy:\n[${worldMatrix[tX][tY].energy}]` : false;
	(objType == 'bot' || objType == 'tree') ? info.value += `\nMinerals:\n[${worldMatrix[tX][tY].minerals}]` : false;
});

function animate() {
	timerId = requestAnimationFrame(animate);
	ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGTH);
	drawElements(worldMatrix);
	drawGrid(ctx);
}

function drawElements(elements) {
	elements.forEach(i => {
		i.forEach(j => {
			if ((j.objType == 'bot') || (j.objType == 'tree') || (j.objType == 'mineral')) {
				j.draw();
			}
		});
	});
}

function drawGrid(ctx) {
	ctx.beginPath();
	for (let i = 0; i < CANVAS_WIDTH; i += GRID_SIZE) {
		ctx.moveTo(i + 0.5, 0);
		ctx.lineTo(i + 0.5, CANVAS_HEIGTH);
	}
	for (let i = 0; i < CANVAS_HEIGTH; i += GRID_SIZE) {
		ctx.moveTo(0, i + 0.5);
		ctx.lineTo(CANVAS_WIDTH, i + 0.5);
	}

	ctx.strokeStyle = 'rgba(240, 240, 240, 0.1)';
	ctx.stroke();
	ctx.closePath();
}

function createTreesAtRandom(count, type = 'tree') {
	for (let index = count; index--;) {
	
		let x, y, e;

		switch (type) {
			case 'tree':
				e = 30;
				break;
			case 'bush':
				e = 25;
				break;
			case 'grass':
				e = 20;
				break;
			default:
				e = 30;
				break;
		}
		if (worldEnergy >= (e * 5)) {
			x = getRandomInt(1, world_width - 2);
			y = getRandomInt(1, world_heigth - 2);
		
			while (worldMatrix[x][y].objType != 'space') {
				x = getRandomInt(1, world_width - 2);
				y = getRandomInt(1, world_heigth - 2);
			}
			worldMatrix[x][y] = treeFactory.create(x, y, type);
			worldMatrix[x][y].energy[0] = e;
			worldMatrix[x][y].minerals[0] = e;
			worldEnergy -= (e  * 5);
		} else {
			console.log(`not enought energy: ${worldEnergy} of ${e * 5} needed`);
			break;
		}
	}
}

function createBotsAtRandom(count, color = 'gray', opt = 'random', genom = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]) {
	for (let index = count; index--;) {
	
		let x, y, e, m;

		e = getRandomInt(128, 256);
		m = getRandomInt(32, 64);

		if (worldEnergy >= (e + m * 4)) {
			x = getRandomInt(1, world_width - 2);
			y = getRandomInt(1, world_heigth - 2);
		
			while (worldMatrix[x][y].objType != 'space') {
				x = getRandomInt(1, world_width - 2);
				y = getRandomInt(1, world_heigth - 2);
			}
			worldMatrix[x][y] = new Bot(x, y, color);
			worldMatrix[x][y].energy[0] = e;
			worldMatrix[x][y].minerals[0] = m;
			worldEnergy -= (e + m * 4);
			if (opt == 'random') {
				worldMatrix[x][y].generateRandomGenom();
			} else if (opt == 'define') {
				worldMatrix[x][y].genom = genom;
			}
		} else {
			console.log(`not enought energy: ${worldEnergy} of ${e + m * 4} needed`);
			break;
		}
	}
}

function checkSummEnergy() {
	let sum = 0;
	worldMatrix.forEach(i => {
		i.forEach(j => {
			if ((j.objType == 'bot') || (j.objType == 'tree')) {
				sum += j.energy[0] + j.minerals[0] * 4;
			}
		});
	});
	return sum;
}

function genomVM(botObj) {
	let adr = 0,
			breakFlag = 0,
			flagMoved = botObj.flagMoved,
			// pointer = null,
			memory = null,
			actCounter = 16;
	let genom = botObj.genom;
	console.log(`Genom is ${genom}`);
	console.log(`Direction = ${botObj.direction}`);
	for (;((breakFlag == 0) && (actCounter > 0) && (flagMoved != 1));) {
		console.log(`****`);
		console.log(`Bot at x = ${botObj.x}, y = ${botObj.y} has actCounter = ${actCounter}`);
		console.log(`genom value at adr ${adr} is ${genom[adr]}`);
		switch (genom[adr]) {
			case 0:
				console.log(`Gen 0 - Мутация случайного гена`);
				console.log(`Старый геном ${genom}`);
				botObj.mutate();
				console.log(`Новый  геном ${genom}`);
				adr = incAdr(adr);
				botDecEnergy(botObj, 1);
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;
/* Двигаемся вперед */
			case 1:
				// adr = incAdr(adr);
				botObj.move();
				flagMoved = 1;
				breakFlag = 1;
				console.log(`Gen 1 - шаг вперед`);
				console.log(`Прерывающая цикл операция`);
				break;
/* Поворачиваемся в случайном направлении */
			case 2:
				console.log(`Gen 2 - поворот в случайном направлении`);
				console.log(`Старое направление ${botObj.direction}`);
				botObj.changeDirection('random');
				console.log(`Новое направление ${botObj.direction}`);
				adr = incAdr(adr);
				botDecEnergy(botObj, 1);
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;
/* Повернуться (исходя из следующего адреса) */
			case 3:
				console.log(`Gen 3 - поворот в зависимости от следующего адреса`);
				console.log(`Старое направление ${botObj.direction}`);
				// делим значение в следующей ячейке на 2, если получаем в остатке 0 - то поворот вправо, иначе - влево
				let x = genom[adr] % 2;
				console.log(`Значение в следующем адресе genom[${adr}] % 2 = ${x}`);		
				let spin; 
				if (x = 0) {
					spin = 'right'
				} else {
					spin = 'left';
				}
				console.log(`Совершаем поворот в направлении ${spin}`);
				botObj.changeDirection(spin);
				console.log(`Новое направление ${botObj.direction}`);
				adr = incAdr(adr);
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;
/* Повернуться (взять направление из памяти) */
			case 4:
			console.log(`Gen 4 - поворот взять направлении из памяти`);
			console.log(`Старое направление ${botObj.direction}`);
			// поворачиваемся в направлении из памяти
			let i;
			memory != null ? i = memory : i = -1;
			if (memory > 0) {
				for (;((i > 0) && (actCounter > 0)); i--) {
					botObj.changeDirection('right');
					actCounter--;
					console.log(`Поворачиваемся направо на 1 сектор`);
					console.log(`Новое направление ${botObj.direction}`);
				}
			} else {
				botObj.changeDirection('random');
				actCounter--;
				console.log(`Поворачиваемся в случайном направлении`);
				console.log(`Новое направление ${botObj.direction}`);
			}
			adr = incAdr(adr);
			memory = null;
			console.log(`Переходим к ячейке ${adr}`);
			break;
/* Кушаем объект спереди */
			case 5:
				console.log(`Gen 5 - Кушаем объект спереди`);
				botObj.eat();
				// adr = incAdr(adr);
				breakFlag = 1;
				console.log(`Прерывающая цикл операция`);
				break;
/* Фотосинтезировать */
			case 6:
				console.log(`Gen 6 - Фотосинтез`);
				console.log(`Энергия бота до фотосинтеза ${botObj.energy}`);
				botObj.getGreenEnergy();
				console.log(`Энергия бота после фотосинтеза ${botObj.energy}`);
				// adr = incAdr(adr);
				breakFlag = 1;
				console.log(`Прерывающая цикл операция`);
				break;
/* Конвертировать собственные минералы в энергию */
			case 7:
				console.log(`Gen 7 - Хемосинтез`);
				console.log(`Энергия бота до Хемосинтеза ${botObj.energy}`);
				console.log(`Минералы бота до Хемосинтеза ${botObj.minerals}`);
				botObj.chemosynthesis();
				console.log(`Энергия бота после Хемосинтеза ${botObj.energy}`);
				console.log(`Минералы бота после Хемосинтеза ${botObj.minerals}`);
				// adr = incAdr(adr);
				breakFlag = 1;
				console.log(`Прерывающая цикл операция`);
				break;
/* Конвертировать собственную энергию в минералы */
			case 8:
				console.log(`Gen 8 - Минерализация`);
				console.log(`Энергия бота до Минерализации ${botObj.energy}`);
				console.log(`Минералы бота до Минерализации ${botObj.minerals}`);
				botObj.mineralisation();
				console.log(`Энергия бота после Минерализации ${botObj.energy}`);
				console.log(`Минералы бота после Минерализации ${botObj.minerals}`);
				// adr = incAdr(adr);
				breakFlag = 1;
				console.log(`Прерывающая цикл операция`);
				break;
/* Проверить, что спереди? */
			case 9:
				console.log(`Gen 9 - Проверка объекта спереди с переходом к команде в адресе + целевое значение`);
				adr = incAdr(adr, returnAdrShiftDependOfFrontObj(botObj, adr));
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;
/* Проверить, голоден ли */
			case 10:
				console.log(`Gen 10 - Проверить голоден ли, переход к команде в адресе + целевое значение`);
				adr = incAdr(adr, returnAdrShiftHunger(botObj, adr));
				actCounter--;
				break;
/* Проверить, атакован ли и положить направление атаки в память */
			case 11:
				console.log(`Gen 11 - Проверить атакован ли, положить направление атаки в память`);
				adr = incAdr(adr);
				memory = returnLastAttackedDirection(botObj);
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;
/* Проверить, атакован ли и перейти к ячейке из памяти в зависимости от результата +1 не атакован, +2/+3 атакован в прошлом/текущем ходу/ +4 в обоих */
			case 12:
				console.log(`Gen 12 - Проверить атакован ли, перейти к команде в адресе в зависимости от результата`);
				adr = incAdr(adr, returnAdrShiftIfAttacked(botObj, adr));
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;
/* Увеличить максимальный возраст на 2 ед */
			case 13:
				console.log(`Gen 13 - Увеличить макс адрес на 2 ед`);
				botObj.longAge();
				botDecEnergy(botObj, 1);
				breakFlag = 1;
				break;			
/* Вернуть адрес смещения - случайное значение между 1 и след. адресом */
			case 14:
				console.log(`Gen 14 - Возвразщаем адрес смещения = случайное значение между 1 и след. адресом`);
				adr = incAdr(adr, returnAdrShiftRandomBetweenValueNextAdr(botObj, adr));
				actCounter--;
				console.log(`Переходим к ячейке ${adr}`);
				break;			
			default:
				console.log(`Нерабочий ген`);
				adr = incAdr(adr);
				actCounter--
				console.log(`Переходим к ячейке ${adr}`);
				break;
		}
		// 
		// actCounter--;
	}
}

// мутация
// идти (вперед)
// повернуться в случайном направлении
// повернуться (взять направление взять из следующего адреса)
// повернуться (взять направление из памяти)
// есть (спереди)
// фотосинтез
// проверить, что спереди?
// * если пусто = 0, родственник = 1, чужой бот = 2, мясо = 3, дерево = 4, минерал = 5, стена = -1, ошибка 255
// проверить голоден ли он?
// проверить атакован ли он? если да - положить направление в "память"
// 

/* увеличиваем адрес, если утыкаемся в хвост, то идем сначала */
function incAdr(adr, increment = undefined) {
	console.log(`incAdr`);
	console.log(`до ${adr}`);
	// increment != undefined ? adr += increment : adr++;
	if (increment != undefined) {
		adr += increment;
	} else {
		adr++;
	}
	adr = adr % GENOM_LENGTH;
	console.log(`после ${adr}`);
	return adr;
}

// ! ToDo: пересмотреть область применения этой функции
/* Вернуть направление, с которого бот аттакован */
function getAttackedDirection(botObj) {
	let direction = botObj.flagAttacked[0];
	return direction;
}

/* В зависимости от типа объекта спереди берем адрес смещения из соседних адресов */
function returnAdrShiftDependOfFrontObj(botObj, adr) {
	let adrShift = 1,
			ax = botObj.x,
			ay = botObj.y,
			frontCoords = getFrontCellCoordinates(botObj.direction, ax, ay); // ! BUG: Какой-то баг...
			console.log(`FrontCoords = ${frontCoords}`);
			if (frontCoords != -1) {
				let frontObj = botCheckDirection(botObj, frontCoords[0], frontCoords[1]);
				switch (frontObj) {
					case 0: // пусто = 0
						adrShift = botObj.genom[incAdr(adr, 1)];
						break;
					case 1: // родственник = 1
						adrShift = botObj.genom[incAdr(adr, 2)];
						break;
					case 2: // чужой бот = 2
						adrShift = botObj.genom[incAdr(adr, 3)];
						break;
					case 3: // мясо = 3
						adrShift = botObj.genom[incAdr(adr, 4)];
						break;
					case 4: // дерево = 4
						adrShift = botObj.genom[incAdr(adr, 5)];
					break;
					case 5: // минерал = 5
						adrShift = botObj.genom[incAdr(adr, 6)];
					break;
					case -1: // стена = -1
						adrShift = botObj.genom[incAdr(adr, 7)];
					break;
					default:
						break;
				}
				console.log(`Объект в клетке x = ${frontCoords[0]}, y = ${frontCoords[1]} ${l1(frontObj)}`);	
			}
			botDecEnergy(botObj, 1);
	return adrShift > 0? adrShift: 1;
}
// ! ToDo: выпилить когда не нужна будет
function l1(frontObj) {
	let res;
	switch (frontObj) {
		case 0:
			res = 'пусто значение из ячейки +1';
			break;
		case 1:
			res = 'родич значение из ячейки +2';
			break;			
		case 2:
			res = 'чужой значение из ячейки +3';
			break;			
		case 3:
			res = 'мясо значение из ячейки +4';
			break;
		case 4:
			res = 'дерево значение из ячейки +5';
			break;			
		case 5:
			res = 'минерал значение из ячейки +6';
			break;
		case -1:
			res = 'стена значение из ячейки +7';
			break;		
		default:
			res = '???';
			break;
	}
	return res;
}

/* В зависимости от того: голоден или нет, - берем адрес смещения из соседних адресов */
function returnAdrShiftHunger(botObj, adr) {
	let adrShift = 1,
			hungry = botObj.flagHungry,
			newAdr;
	switch (hungry) {
		// ! ToDo: Просмотреть код внимательно, кажется что он делает не то, что задумано
		case 0: // не голоден = 0
			adrShift = botObj.genom[incAdr(adr, 1)];
			newAdr = adr + 1;
			break;
		case 1: // голоден = 1
			adrShift = botObj.genom[incAdr(adr, 2)];
			newAdr = adr + 2;
			break;
		default:
			break;
	}
	console.log(`Бот ${hungry = 0 ? 'не голоден' : 'голоден'}, адрес смещения берем из genom[${newAdr}] = ${adrShift}`);
	botDecEnergy(botObj, 1);
	return adrShift;
}

/* В зависимости от того: атакован или нет - возвращаем значение направления, с которого атакован */
function returnLastAttackedDirection(botObj) {
	let attackedNow = botObj.flagAttacked[0],
			attackedLastTurn = botObj.flagAttacked[1];
			botDecEnergy(botObj, 1);
	if (attackedNow > 0) {
		return attackedNow;
	} else if (attackedLastTurn > 0) {
		return attackedLastTurn;
	} else {
		return null;
	}
}

function returnAdrShiftIfAttacked(botObj, adr) {
	let adrShift = 0,
			newAdr = 1;
	// не атакован - 00
	// был атакован в прошлом ходу - 01
	// атакован сейчас - 10
	// атакован и сейчас и в прошлом ходу 11
	if (botObj.flagAttacked[1] > 0) {
		newAdr += 1;
	}
	if (botObj.flagAttacked[0] > 1) {
		newAdr += 2;
	}
	adrShift = botObj.genom[adr+newAdr];
	botDecEnergy(botObj, 1);
	return adrShift;
}

/* Мутация в случайном гене */
function genomMutate(botObj) {
	let botGenom = botObj.genom;
	let pos = getRandomInt(0, botGenom.length - 1);
	let oldGen = botGenom[pos];
	while (oldGen == botGenom[pos]) {
		botGenom[pos] = getRandomInt(0, GENS);
	}
	return botGenom;
}


function unshiftFlagAttacked(worldMatrix) {
	for(let j = 0, xJ = worldMatrix.length; j < xJ; j++) {
		for(let i = 0, xI = worldMatrix[j].length; i < xI; i++) {
			let elem = worldMatrix[j][i];
			if (elem.objType == 'bot') {
				elem.flagAttacked.pop();
				elem.flagAttacked.unshift(0);
			}
		}
	}
}

// ! ToDo: добавить изменение флага атакован если получает урон от другого бота

/* В зависимости  от значения в след. ячейке берем адрес смещения (random[1, value]) */
function returnAdrShiftRandomBetweenValueNextAdr(botObj, adr) {
	let adrShift = getRandomInt(1, botObj.genom[adr + 1]);
	botDecEnergy(botObj, 1);
	console.log(`${adrShift}`);
	return adrShift > 0 ? adrShift: 1;
}

/* ############################################## */

// timerId = setTimeout(tick, 500);

function tick() {
	logger();
	updateMatrix();
	/* Выставляем флаги перемещения ботов в 0 */
	worldMatrix.forEach(i => {
		i.forEach(j => {
			if (j.objType == 'bot') {
				j.clearMoveParams();
			}
		});
	});

	timerId = setTimeout(tick, render_speed); // (*)
	worldTime++;
	if ((worldTime >= STEPS) || (pause == 1)) {
		clearTimeout(timerId);
	}
}

/* Функция обновления значение в целевом поле в боковом меню */
function updateValueAtField(targetField, targetValue) {
	const xField = document.getElementById(targetField);
	xField.value = targetValue;
}


function setPause() {
	if (pause != 1) {
		pause = 1;
		document.getElementById("play").src = "images/play_button.jpg";
	} else {
		pause = 0;
		timerId = setTimeout(tick, 200);
		document.getElementById("play").src = "images/pause_button.jpg";
	}
}

/* Добавляем обработчик нажатия кнопку Play */
const btn = document.querySelector('.play-button');
btn.addEventListener('click', setPause);

/* Добавляем обработчик изменения пикера скорости отрисовки */
const render_speed_picker = document.getElementById('render-speed-picker'),
			render_speed_output = document.getElementById('render-speed-output');
render_speed_picker.addEventListener('change', () => {
	render_speed_output.value = render_speed_picker.value;
	render_speed = 320 / render_speed_picker.value;
	// console.log(`Render speed is: ${render_speed}`);
});
render_speed_output.addEventListener('change', () => {
	render_speed_picker.value = render_speed_output.value;
	render_speed = 320 / render_speed_picker.value;
});

/* Добавляем обработчик нажатия на кнопку Generate */
const generate_button = document.getElementById('generate-button');
generate_button.addEventListener('click', generateFromParams);

function generateFromParams() {
	let bots,
			color = colors[2][0],
			trees,
			bush,
			grass;
	bots = document.getElementById('bots-count').value;
	createBotsAtRandom(bots, color, 'random');
	trees = document.getElementById('trees-count').value;
	createTreesAtRandom(trees, 'tree');
	bush = document.getElementById('bush-count').value;
	createTreesAtRandom(bush, 'bush');
	grass = document.getElementById('grass-count').value;
	createTreesAtRandom(grass, 'grass');
	logger();
}

/* Добавляем обработчик нажатия на кнопку Clear */
const clear_button = document.getElementById('clear-button');
clear_button.addEventListener('click', clearTheWorld);

function clearTheWorld() {
	emptySpaceGenerator(worldMatrix);
	buildTheWorldWall(worldMatrix);
	worldTime = 0;
	worldEnergy = world_width * world_heigth * ENERGY_PER_CELL;
	(pause != 1) ? setPause() : false;
	logger();
}

// ! ToDo: Добавить обработчик выбора цвета

function updateMatrix() {
	worldMatrix.forEach(i => {
		i.forEach(j => {
			if (j.objType == 'tree') {
				j.growth();
				j.checkMakeChild();
				j.incAge();
				j.isAlive();
			}
			if (j.objType == 'bot') {
				genomVM(j);
				j.checkMakeChild();
				j.isSleeping();
				j.incAge();
				j.isAlive();
			}
			if (j.objType == 'mineral') {
				j.incAge();
				j.isAlive();
			}
		});
	});
	unshiftFlagAttacked(worldMatrix);
}

function logger() {
	console.clear();
	console.log(`step ${worldTime}`);
	console.log(`free energy :${worldEnergy}`);
	console.log(`full energy :${checkSummEnergy()}`);
	updateValueAtField('turn-counter', worldTime);
	updateValueAtField('free-energy', worldEnergy);
	updateValueAtField('used-energy', checkSummEnergy());
}

const colors = [
	['rgb(255, 32, 32)', 'Red'],// 0 - Красный (светлый)
	['rgb(255, 69,  0)', 'DarkOrange'],// 1 - Красно-оранжевый
	['rgb(255,165,  0)', 'Orange'],// 2 - Оранжевый
	['rgb(255,255,  0)', 'Yellow'],// 3 - Желтый
	['rgb(127,255,  0)', 'Chartreuse'],// 4 - Желто-зеленый (кислотный зеленый)
	['rgb(  0,255,  0)', 'Lime'],// 5 - Лаймовый зеленый
	['rgb(128,128, 64)', 'Olive'],// 6 - Оливковый
	['rgb(  0,128,  0)', 'Green'],// 7 - Зеленый
	['rgb(127,255,212)', 'Aquamarine'],// 8 - Аквамарин
	['rgb(  0,255,255)', 'Aqua'],// 9 - Голубой (морская волна)
	['rgb( 30,144,255)', 'DodgerBlue'],// 10 - Темно-голубой (dodger blue)
	['rgb(  0,  0,255)', 'Blue'],// 11 - Синий
	['rgb(255,  0,255)', 'Fuchsia'],// 12 - Розовый (magenta)
	['rgb(255, 20,147)', 'DeepPink'],// 13 - Насыщенный розовый
	['rgb(148,  0,211)', 'DarkViolet'],// 14 - Фиолетовый
	['rgb(255,255,240)', 'Ivory'],// 15 - Кость
	['rgb(244,164, 96)', 'SandyBrown'],// 16 - Светло-коричневый
	['rgb(139, 69, 19)', 'SaddleBrown'],// 17 - Темно-коричневый
	['rgb(  0,  0,  0)', 'Black'],// 18 - Черный
	['rgb(255,255,255)', 'White'],// 19 - Белый
];


const treeFactory = new TreeFactory();
emptySpaceGenerator(worldMatrix);
buildTheWorldWall(worldMatrix);

animate();