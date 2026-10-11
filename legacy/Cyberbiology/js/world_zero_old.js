'use strict'

const CANVAS_WIDTH = 800,
	CANVAS_HEIGTH = 600,
	GENOM_LENGTH = 16,
	WORLD_X = 20,
	WORLD_Y = 20, // ! Bug: Найти баг, из-за которого падает прила при разных значениях x/y
	MUTATION_FACTOR = 15,
	GENS = 11, // количество разных генов
	STEPS = 1000;

let worldTime = 0;
let worldEnergy = 100000;
let fullWorldEnergy = 0;

function Bot(coordX, coordY) {
		this.objType = 'bot';
		this.age = [0,1024];
		this.posX = coordX;
		this.posY = coordY;
		this.direction = 1;
		this.flagAttacked = [0,0]; // позиция 0 - в текущем ходе, 1я - в предыдущем; 1-8 - направление, откуда атакаван 0 - не атакован
		this.flagSleeping = 0;
		this.flagHungry = 0;
		this.flagMoved = 0;
		this.flagAlive = 1;
		this.energy = [512,1024];
		this.minerals = [8,256];
		this.speed = 100;
		this.genom = [];
		this.eat = [0,0,0,0]; // кушает 0 - растения, 1 - других ботов, 2 - мясо, 3 - минералы
		// this.randomGenom = function () {
		// 	this.genom = randomGenomGenerator();
		// };
}

function Space() {
	this.objType = 'space';
	// this.energy = [271,8192];
	// TODO: добавить рассеивание энергии в пространстве, поглошение ее деревьями
	// TODO: и превращение минералов в энергию после "смерти". Также, добавить
	// TODO: прямое получение энергии пространства из клетки пустого пространства
	// TODO: при переходе ботом в нее. Бот "сгорает", если энергия в клетке слишком большая.
	// TODO: Добавить ген проверки температуры в клетке по направлению взгляда.
}

function Tree(coordX, coordY) {
	this.objType = 'tree';
	this.age = [0,512];
	this.posX = coordX;
	this.posY = coordY;
	this.energy = [300,2048];
	this.minerals = [200,2048];
	this.flagAlive = 1;
	this.genus = 'tree';
}

function Meat(coordX, coordY) {
	this.objType = 'meat';
	this.age = [0,64];
	this.posX = coordX;
	this.posY = coordY;
	this.energy = [20,256];
	this.minerals = [20,2048];
	this.flagAlive = 1;  
}

function Mineral(coordX, coordY) {
	this.objType = 'mineral';
	this.age = [0,128];
	this.posX = coordX;
	this.posY = coordY;
	this.energy = [20,256];
	this.minerals = [2048,4096];
	this.flagAlive = 1;  
}

function Wall(coordX, coordY) {
	this.objType = 'wall';
}

function create2DArray(rows = 5, columns = 5) {
	let arr = new Array(rows);
	for (let i = 0; i < arr.length; i++) {
		arr[i] = new Array(columns);
	}
	return arr;
}

function emptySpaceGenerator(worldObj) {
	for(let j = worldObj.length - 1; j--;) {
		for(let i = worldObj[j].length - 1; i--;) {
			worldObj[j][i] = new Space();
		}
	}
}

// * возвращает геном (массив длиной 16 из случайных чисел от 0 до GENS)
function randomGenomGenerator(genomLength = 16, genomLowAdr = 0, genomHighAdr = GENS) {
	let GENOM = [];
	for (let x = genomLength; x--;) {
		GENOM.push(getRandomInt(genomLowAdr, genomHighAdr));
	};
	return GENOM;
}

// * возвращает случайное число в диапазоне [min, max]
function getRandomInt(min, max) {
	if (min < max) {
		return Math.floor(Math.random() * (max - min + 1)) + min;
	} else {
		return Math.floor(Math.random() * (min - max + 1)) + max;
	}
}

// * возвращает целый показатель степени, в которую нужно возвести 2 для получения числа x
function powerOfTwo(x) {
	let pow = 1;
	for (;2 <= x / 2; pow++) {
		x /= 2;
	}
	return pow;
}

let worldMatrix = create2DArray(WORLD_X, WORLD_Y);

emptySpaceGenerator(worldMatrix);

buildTheWorldWall(worldMatrix);

for (let index = 70; index--;) {
	
	let x, y;

	x = getRandomInt(1, WORLD_X - 1);
	y = getRandomInt(1, WORLD_Y - 1);

	while (worldMatrix[x][y].objType != 'space') {
		x = getRandomInt(1, WORLD_X - 1);
		y = getRandomInt(1, WORLD_Y - 1);
	}

	createNewBot(x, y, 'randomGenom');
	worldEnergy -= (worldMatrix[x][y].energy[0] + worldMatrix[x][y].minerals[0] * 4);
}

for (let index = 5; index--;) {
	
	let x, y, m, e;

	x = getRandomInt(1, WORLD_X - 1);
	y = getRandomInt(1, WORLD_Y - 1);

	while (worldMatrix[x][y].objType != 'space') {
		x = getRandomInt(1, WORLD_X - 1);
		y = getRandomInt(1, WORLD_Y - 1);
	}
	e = getRandomInt(32, 128);
	m = getRandomInt(128, 512);
	createNewMineral(x, y, e, m);
	worldEnergy -= (worldMatrix[x][y].energy[0] + worldMatrix[x][y].minerals[0] * 4);
	
}


for (let index = 3; index--;) {
	
	let x, y;

	x = getRandomInt(1, WORLD_X - 1);
	y = getRandomInt(1, WORLD_Y - 1);

	while (worldMatrix[x][y].objType != 'space') {
		x = getRandomInt(1, WORLD_X - 1);
		y = getRandomInt(1, WORLD_Y - 1);
	}
	createNewTree(x, y);
	worldEnergy -= (worldMatrix[x][y].energy[0] + worldMatrix[x][y].minerals[0]  * 4);
}

for (let index = 3; index--;) {
	
	let x, y;

	x = getRandomInt(1, WORLD_X - 1);
	y = getRandomInt(1, WORLD_Y - 1);

	while (worldMatrix[x][y].objType != 'space') {
		x = getRandomInt(1, WORLD_X - 1);
		y = getRandomInt(1, WORLD_Y - 1);
	}
	createNewTree(x, y, 'grass');
	worldEnergy -= (worldMatrix[x][y].energy[0] + worldMatrix[x][y].minerals[0]  * 4);
}

for (let index = 3; index--;) {
	
	let x, y;

	x = getRandomInt(1, WORLD_X - 1);
	y = getRandomInt(1, WORLD_Y - 1);

	while (worldMatrix[x][y].objType != 'space') {
		x = getRandomInt(1, WORLD_X - 1);
		y = getRandomInt(1, WORLD_Y - 1);
	}
	createNewTree(x, y, 'bush');
	worldEnergy -= (worldMatrix[x][y].energy[0] + worldMatrix[x][y].minerals[0]  * 4);
}


function main(worldObj) {
	clearMoveParams(worldObj);
	unshiftFlagAttacked(worldObj);
	vmsFunc(worldObj);
	checkSummEnergy(worldObj);
}

// * основная функция, которая обходит двумерный мировой массив и запускает другие функции, в зависимости от объекта на карте
function vmsFunc(worldObj) {
	for(let j = 0; j < worldObj.length; j++) {
		for(let i = 0; i < worldObj[j].length; i++) {
			let elem = worldObj[j][i];
						if (elem.objType == 'bot') {
								if (elem.flagMoved == 0) {
					genomVM(elem, worldObj);
					if (botCanMakeChild(elem)) {
						botCreateChild(elem, worldObj)
					}
				}
				elem.age[0] += 1;
						} else if (elem.objType == 'tree') {
				treeVM(elem, worldObj);
				elem.age[0] += 1;
				if (elem.age[0] >= elem.age[1]) {
					treeToMineral(elem, worldObj);
				}
						} else if (elem.objType == 'meat') {
				meatVM(elem, worldObj);
				elem.age[0] += 1;
				if (elem.age[0] >= elem.age[1]) {
					meatToMineral(elem, worldObj);
				}
						} else if (elem.objType == 'mineral') {
				mineralsVM(elem);
				elem.age[0] += 1;
				if (elem.age[0] >= elem.age[1]) {
					mineralToEnergy(elem, worldObj);
				}
						} else if (elem.objType == 'space') {
						}
		}
	}
}

function checkSummEnergy(worldObj) {
	fullWorldEnergy = worldEnergy;
	for(let j = 0; j < worldObj.length; j++) {
		for(let i = 0; i < worldObj[j].length; i++) {
			let elem = worldObj[j][i];
						if (elem.energy != undefined) {
								fullWorldEnergy += elem.energy[0];
						}
			if (elem.minerals != undefined) {
								fullWorldEnergy += (elem.minerals[0] * 4);
						}
		}
	}
}

// * функция, которая в конце хода переводит флаги движения всех ботов в состояние 0
function clearMoveParams(worldObj) {
	for(let j = 0; j < worldObj.length; j++) {
		for(let i = 0; i < worldObj[j].length; i++) {
			let elem = worldObj[j][i];
						if (elem.objType == 'bot') {
								elem.flagMoved = 0;
						}
		}
	}
}

function unshiftFlagAttacked(worldObj) {
	for(let j = 0; j < worldObj.length; j++) {
		for(let i = 0; i < worldObj[j].length; i++) {
			let elem = worldObj[j][i];
						if (elem.objType == 'bot') {
								elem.flagAttacked.pop();
				elem.flagAttacked.unshift(0);
						}
		}
	}
}

// * функция обработки генома бота
function genomVM(botObject, worldObj) {
	let breakFlag = 0,
	actCounter = 16,
	adr = 0;

	let energy,
	direction = botObject.direction, // * направление взгляда бота 1 сев, 2 сев-вос, 3 восток ... 8 сев-зап, 0 - никуда
	posX = botObject.posX,
	posY = botObject.posY,
	botGenom = botObject.genom,
	botMoved = botObject.flagMoved,
	attacked = botCheckFlagAttacked(botObject),
	botSpeed;

	for (;((breakFlag == 0) && (actCounter >= 0) && (botMoved != 1));) {
		energy = botObject.energy[0];
		botSpeed = setSpeed(botObject);
		let frontCoordinates = getFrontCellCoordinates(direction, posX, posY);
		let frontObjectType;
		let frontX;
		let frontY;
		if (frontCoordinates != -1) {
			frontX = frontCoordinates[0];
			frontY = frontCoordinates[1];
			frontObjectType = worldObj[frontX][frontY].objType;		
		}

		switch (botGenom[adr]) {
			case 0: // Mutate random gen
				adr = incAdr(adr);
				energy = decEnergy(energy, 1);
				genomMutate(botGenom);
				actCounter--;
				break;
			case 1: // Move front
			// Понять, что за объект в координатах спереди (по линии взгляда)
			// Если не смотрит никуда (спит), то переходим к команде в адресе +1
			// Если спереди есть стена, то переходим к команде в адресе +2
			// Если спереди не пустое пространство и не стена, то переходим к команде в адресе +3
			// Если спереди пустое пространство, то шагаем на клетку вперед переходим к команде +4
				if  (energy <= (2 * botSpeed + 1)) {
					if (direction != 0) {
						direction = 0;
						energy = decEnergy(energy, 1);
						break;
					}
				} else {
					if (frontObjectType == 'wall') {
						adr = jumpAdr(adr, 2);
						energy = decEnergy(energy, 1);
					} else if ((frontObjectType == 'bot') || (frontObjectType == 'tree') || (frontObjectType == 'mineral')) {
						adr = jumpAdr(adr, 3);
						energy = decEnergy(energy, 1);
					} else if (frontObjectType == 'space') {
						botMove(posX, posY, frontX, frontY);
						adr = jumpAdr(adr, 4);
						breakFlag = 1; // Перемещение это прерывающая активность операция 
						botObject.flagMoved = 1;
						energy = decEnergy(energy, botSpeed); //при перемещении уменьшаем энергию на величину botSpeed
					} else if (direction == 0) {
						adr = incAdr(adr);
						energy = decEnergy(energy, 1); //спим - тратим 1 ед энергии
					}
				}
				breakFlag = 1;
				break;
			case 2: // Bot change direction right
				adr = incAdr(adr);
				direction = botChangeDirection(direction, 'right');
				energy = decEnergy(energy, Math.ceil(botSpeed/8));
				actCounter--;
				break;
			case 3: // Bot change direction left
				adr = incAdr(adr);
				direction = botChangeDirection(direction, 'left');
				energy = decEnergy(energy, Math.ceil(botSpeed/8));
				actCounter--;
				break;
			case 4: // Bot change direction to random
				adr = incAdr(adr);
				direction = botChangeDirection();
				energy = decEnergy(energy, Math.ceil(botSpeed/8));
				actCounter--;
				break;
			case 5: // Bot checks his energy lvl
			// Если энергия от 0 до 9% то переходим к команде в адресе +1, 10-59% => +2, 60-99% => +3, 100% => +4
				let eLvl = checkOwnParamLvl(botObject);
				if (eLvl = 0) {
					adr = incAdr(adr);
				} else if ((eLvl >= 1) && (eLvl <= 5)) {
					adr = jumpAdr(adr, 1);
				} else if ((eLvl >= 6) && (eLvl <= 9)) {
					adr = jumpAdr(adr, 2);
				} else if (eLvl = 10) {
					adr = jumpAdr(adr, 3);
				}
				energy = decEnergy(energy, 1);
				actCounter--;
				break;
			case 6: // Bot eat tree from front cell
				if (frontObjectType == 'tree') {
					energy = botEatFrontObject(botObject, frontX, frontY, 'tree');
					energy = decEnergy(energy, 1);
					breakFlag = 1;
					botObject.eat[0] += 1;
				}
				
				adr = incAdr(adr);
				actCounter--;
				break;
			case 7: // Bot eat meat from front cell
			if (frontObjectType == 'meat') {
				energy = botEatFrontObject(botObject, frontX, frontY, 'meat');
				energy = decEnergy(energy, 1);
				breakFlag = 1;
				botObject.eat[1] += 1;
			}
			
			adr = incAdr(adr);
			actCounter--;
			break;
			case 8: // Bot eat mineral from front cell
				if (frontObjectType == 'mineral') {
					energy = botEatFrontObject(botObject, frontX, frontY, 'mineral');
					energy = decEnergy(energy, 1);
					breakFlag = 1;
					botObject.eat[3] += 1;
				}
				
				adr = incAdr(adr);
				actCounter--;
				break;
			case 9: // Bot bite another bot from front cell
			// ToDo: Вынести "драку" ботов в отдельную функцию
				if (frontObjectType == 'bot') {
					let frontBot = worldObj[frontX][frontY],
					chanceToWin = 0,
					attEnergy = 1 + checkOwnParamLvl(botObject, 'energy'),
					attMinerals = 1 + checkOwnParamLvl(botObject, 'minerals'),
					defEnergy = 1 + checkOwnParamLvl(frontBot, 'energy'),
					defMinerals = 1 + checkOwnParamLvl(frontBot, 'minerals'),
					attHungryLvl = 10 - checkOwnParamLvl(botObject, 'energy'); // Чем аттакующий голоднее, чем яростнее нападает

					chanceToWin = parseInt(attHungryLvl * attEnergy / (attEnergy + defEnergy) - defMinerals / (attMinerals + defMinerals));

					let reverseDirection = (direction + 4) % 8;
					if (chanceToWin >= 1) {
						energy = botAttackBot(botObject, frontX, frontY, reverseDirection);
						energy = decEnergy(energy, attHungryLvl);
					}
					breakFlag = 1;
					botObject.eat[2] += 1;
				}
				
				adr = incAdr(adr);
				actCounter--;
				break;
			case 10: // Bot check attacked flag
				/* Если не атакован, то переходим к команде в адресе +5, если атакован, то к следующей за проверкой */
				if (attacked = 0) {
					adr = jumpAdr(adr, 5);
				} else if ((attacked >= 1) && (attacked <= 8)) {
					adr = incAdr(adr);
				}
				energy = decEnergy(energy, 1);
				actCounter--;
				break;
			case 11: // Bot spin face to face to attacked direction
				/* Если атакован, то переходим поворачиваемся "лицом" в направлении атаки, иначе поворачиваемся в случайном направлении */
				// let attacked = botCheckFlagAttacked(botObject);
				if (attacked = 0) {
					direction = botChangeDirection();
				} else if ((attacked >= 1) && (attacked <= 8)) {
					let newDirection = (attacked + 4) % 8;
					botChangeDirectionСonditional(botObject, newDirection);
					energy = decEnergy(energy, 3);
				}
				adr = incAdr(adr);
				energy = decEnergy(energy,1);
				actCounter--;
				break;
			default:
				adr = 0;
				breakFlag = 1;
				break;
		}

		botObject.direction = direction;
		botObject.energy[0] = energy;
	}
	checkBotAge(botObject);
	checkBotMainParam(botObject, 'energy');
	checkBotMainParam(botObject, 'minerals');
}

function jumpAdr(adr, step) {
	adr += step;
	adr = adr % GENOM_LENGTH;
	return adr;
}

function incAdr(adr) {
	adr++;
	adr = adr % GENOM_LENGTH;
	return adr;
}

function incParam(paramsArray, increment) {
	(paramsArray[0] + increment <= paramsArray[1]) ?
	(paramsArray[0] += increment) :
	(paramsArray[0] = paramsArray[1]);
	if (paramsArray[0] + increment <= 0) {
		paramsArray[0] = 0;
	} 
	return paramsArray[0];
}

function decEnergy(energy, increment) {
	(energy - increment > 0) ?
	(energy -= increment) :
	(energy = 0);
	worldEnergy += increment;
	return energy;
}

function genomMutate(botGenom) {
	let pos = getRandomInt(0, botGenom.length - 1);
	let oldGen = botGenom[pos];
	while (oldGen == botGenom[pos]) {
		botGenom[pos] = getRandomInt(0, 5);
	}
	return botGenom;
}

function genomRecombinate(botGenom) {
	let pos1 = getRandomInt(0, botGenom.length - 1);
	let pos2, temp;
	pos2 = getRandomInt(0, botGenom.length - 1);
	while (pos2 == pos1) {
		pos2 = getRandomInt(0, botGenom.length - 1);
	}
	temp = botGenom[pos1] ;
	botGenom[pos1] = botGenom[pos2];
	botGenom[pos2] = temp;
	return botGenom;
}

function botMove(coordX, coordY, newX, newY) {
		if ((worldMatrix[coordX][coordY].objType == 'bot') && (worldMatrix[newX][newY].objType == 'space')) {
				let temp = worldMatrix[coordX][coordY];
				temp['posX'] = newX;
				temp['posY'] = newY;
				worldMatrix[newX][newY] = temp;
				worldMatrix[coordX][coordY] = new Space();
		} else {
				return false;
		}
}

// * Вычисление координат клетки в направлении взгляда бота
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
				if (botPosX < WORLD_X - 1 && botPosY != 0) {
					coordsXY = [botPosX + 1, botPosY - 1];	
				} else {
					return -1;
				}
				break;
			case 3:
				if (botPosX < WORLD_X - 1) {
					coordsXY = [botPosX + 1, botPosY];	
				} else {
					return -1;
				}
				break;
			case 4:
			if (botPosX < WORLD_X - 1 && botPosY < WORLD_Y - 1) {
				coordsXY = [botPosX + 1, botPosY + 1];	
			} else {
				return -1;
			}
			break;
			case 5:
			if (botPosY < WORLD_Y - 1) {
				coordsXY = [botPosX, botPosY + 1];	
			} else {
				return -1;
			}
			case 6:
			if (botPosX > 0 && botPosY < WORLD_Y - 1) {
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

// * Бот поворачивается на 1 сектор в направлении spin, относительно текущего направления
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

// TODO: Change direction conditional
function botChangeDirectionСonditional(botObject, dir) {
	if ((dir != 0) && (dir >= 1) && (dir <= 8)) {
		botObject.direction = dir;
	} else {
		botObject.direction = getRandomInt(1, 8);
	}
}

// * Функция проверки объекта в указанных координатах
function botCheckDirection(botGenom, worldArray, coordX, coordY) { // * получаем координаты, возвращаем ответ 
	// * если пусто = 0, родственник = 1, чужой бот = 2, дерево = 3, минерал = 4, стена = -1, ошибка 255
	let objType = worldArray[coordX][coordY].objType;
	let x;
	switch (objType) {
		case 'space':
			x = 0;
			break;
		case 'bot':
			let frontBotGenom = worldArray[coordX][coordY].genom;
			isRelative(botGenom, frontBotGenom) == 1 ? x = 1 : x = 2;
		case 'tree':
			x = 3;
			break;
		case 'mineral':
			x = 4;
			break;
		case 'wall':
			x = -1;
			break;
		default:
			x = 255;
			break;
	}
	return x;
}

// TODO: отрисовка канваса - должна вызываться каждый тик. Пока что рисуем просто в консольку
function render(arr) {
	for(let j = 0; j < arr.length; j++) {
		let line = '';
		for(let i = 0; i < arr[j].length; i++) {
			if (arr[j][i] != undefined && arr[j][i].objType == 'bot') {
				line += colorBot(arr[j][i]);
			} else if (arr[j][i] != undefined && arr[j][i].objType == 'tree') {
				line += `\x1b[32m${'*'}`;
			} else if (arr[j][i] != undefined && arr[j][i].objType == 'mineral') {
				line += `\x1b[0m${'o'}`;
			} else if (arr[j][i] != undefined && arr[j][i].objType == 'meat') {
				line += `\x1b[31m${'+'}`;
			} else if (arr[j][i] != undefined && arr[j][i].objType == 'wall') {
				line += `\x1b[90m${'#'}`;
			} else {
				line += `\x1b[0m${' '}`;
			}
		}
		console.log(`${line}`);
	}
}

function colorBot(botObject) {
	let eatArr = botObject.eat,
	line = '';
	if ((eatArr[0] > 0) && (eatArr[1] == 0) && (eatArr[2] == 0) && (eatArr[3] == 0)) { // green => растения
		line = `\x1b[32m${'x'}`;
		// console.log(`${eatArr} im green`);
	} else if ((eatArr[0] == 0) && ((eatArr[1] > 0) || (eatArr[2] > 0)) && (eatArr[3] == 0)) { // red => мясо
		line = `\x1b[31m${'x'}`;
		// console.log(`${eatArr} im red`);
	} else if ((eatArr[0] == 0) && (eatArr[1] == 0) && (eatArr[2] == 0) && (eatArr[3] > 0)) { // dark grey => минералы 
		line = `\x1b[90m${'x'}`;
		// console.log(`${eatArr} im dark grey`);
	} else if (((eatArr[0] > 0) || (eatArr[3] > 0)) && ((eatArr[1] > 0) || (eatArr[2] > 0))) { // magenta ~ purple => смешанное
		line = `\x1b[35m${'x'}`;
		// console.log(`${eatArr} im purple`);
	} else if ((eatArr[0] > 0) && (eatArr[1] == 0) && (eatArr[2] == 0) && (eatArr[3] > 0)) { // yellow => не мясо
		line = `\x1b[33m${'x'}`;
		// console.log(`${eatArr} im yellow`);
	} else {
		line = `\x1b[36m${'x'}`; // cian ~ marina blue => ничего?
		// console.log(`${eatArr} im cian`);
	}
	return line;
}

// * Создаем стену по краю мира
function buildTheWorldWall(arr) {
	for (let i = arr.length-1; i--;) {
		arr[0][i] = new Wall(); // top border
 		arr[i][arr[0].length-1] = new Wall(); // right border
		arr[arr.length-1][i+1] = new Wall(); // bottom border
		arr[i+1][0] = new Wall(); // left border
		
	}
}

// * Tree VM
//дерево  приращивает каждый ход энергию и минералы, по достижению определенного возраста умирает
//и оставляет всю накопленную энергию в минерале, которая "остывая" превращается в минеральную составляющую
//дерева energy -> minerals
//Если у дерева возраст > определенного значения и достаточно энергии и минералов, создает еще одно дерево
//в определенном радиусе
function treeVM(treeObject, worldObj) {
	let posX = treeObject.posX,
	posY = treeObject.posY,
	treeEnergy = treeObject.energy[0],
	maxEnergy = treeObject.energy[1],
	treeMinerals = treeObject.minerals[0],
	maxMinerals = treeObject.minerals[1],
	energyLvl,
	mineralsLvl,
	// ageLvl,
	age,
	treeGenusType = 3,
	growSpeed = 1; // 1 - grass, 2 - bush, 3 - tree

	if (treeObject.genus == 'grass') {
		treeGenusType = 1;
	} else if (treeObject.genus == 'bush') {
		treeGenusType = 2;
	}

	growSpeed = Math.pow(2, (treeGenusType) - 1) + 3; // ! ToDo: Вынести вычисление скорости роста в отдельную функцию при создании дерева

	if (growSpeed >= Math.floor(worldEnergy  / 5)) {
		growSpeed = Math.floor(worldEnergy / 5);
	}

	worldEnergy -= growSpeed * 5;

	treeEnergy = incParam(treeObject.energy, growSpeed);
	worldObj[posX][posY].energy[0] = treeEnergy;
	treeMinerals = incParam(treeObject.minerals, growSpeed);
	worldObj[posX][posY].minerals[0] = treeMinerals;
	
	energyLvl = checkOwnParamLvl(treeObject);
	mineralsLvl = checkOwnParamLvl(treeObject, 'minerals');
	age = treeObject.age[0];

	if ((energyLvl >= 7) && (mineralsLvl >= 7) && (age >= 40)) {
		treeMakeChild(treeObject, treeGenusType, worldObj)
	}
}

// * Функция создания нового дерева в определенных координатах
function createNewTree(coordX, coordY, genusType = 'tree') {
	let newTree = new Tree(coordX, coordY);

	if ((genusType == 'grass') || (genusType == 'bush')) {
		newTree.genus = genusType;
		if (genusType == 'grass') {
			newTree.energy[1] = 256;
			newTree.minerals[1] = 256;
			newTree.age[1] = 256;
		} else {
			newTree.energy[1] = 1024;
			newTree.minerals[1] = 1024;
			newTree.age[1] = 1024;
		}
	}

	if (((newTree.energy[0] + newTree.minerals[0] * 4) > worldEnergy)){
		if ((worldEnergy >= 5)) {
			newTree.energy[0] = Math.floor(worldEnergy, 5) + worldEnergy % 5;
			newTree.minerals[0] = Math.floor(worldEnergy, 5) * 4;
		} else {
			newTree.energy[0] = Math.floor(worldEnergy, 2);
			newTree.minerals[0] = Math.floor(worldEnergy, 2) + worldEnergy % 2;
		}

		worldEnergy = 0;
	} else {
		worldEnergy -= (newTree.energy[0] + newTree.minerals[0] * 4);
	}

	worldMatrix[coordX][coordY] = newTree;
}

function treeMakeChild(treeObject, treeGenusType, worldObj) {
	let parentX = treeObject.posX,
		parentY = treeObject.posY,
		newTreeX,
		newTreeY;

	for (let index = 15; index--; ) {
		let difX = getRandomInt(-treeGenusType, treeGenusType),
			difY = getRandomInt(-treeGenusType, treeGenusType);
		
		while ((difX == 0) && (difY == 0)) {
			difX = getRandomInt(-treeGenusType, treeGenusType),
			difY = getRandomInt(-treeGenusType, treeGenusType);
		}
	
		newTreeX = parentX + difX;
		newTreeY = parentY + difY;
	
		if ((newTreeX > 0 && newTreeX < WORLD_X) && (newTreeY > 0 && newTreeY < WORLD_Y)) {
			if (worldObj[newTreeX][newTreeY].objType == 'space') {
				let temp = Math.round(worldObj[parentX][parentY].energy[0] / 2);
				createNewTree(newTreeX, newTreeY, treeGenusType);
				worldObj[newTreeX][newTreeY].energy[0] = temp;
				worldObj[parentX][parentY].energy[0] = worldObj[parentX][parentY].energy[0] - temp;
				temp = Math.round(worldObj[parentX][parentY].minerals[0] / 2);
				worldObj[newTreeX][newTreeY].minerals[0] = temp;
				worldObj[parentX][parentY].minerals[0] = worldObj[parentX][parentY].minerals[0] - temp;
				index = 0;
			} else {
				continue;
			}		
		}
	}
}

// TODO: Minerals VM
function mineralsVM(params) {
	return false;
}

function createNewMineral(coordX, coordY, ...[energy, minerals]) {
	let newMineral = new Mineral(coordX, coordY);

	if (energy != undefined) {
		newMineral.energy[0] = energy;
	}

	if (minerals != undefined) {
		newMineral.minerals[0] = minerals;
	}

	worldMatrix[coordX][coordY] = newMineral;
}

// Meat VM
function meatVM(meatObject, worldObj = worldMatrix) {
	crystalization(meatObject, worldObj);
	if (meatObject.age[0] >= meatObject.age[1]) {
		revertAliveFlag(meatObject);
	}
}

function crystalization(targetObject, worldObj = worldMatrix) {
	if ((targetObject.energy[0] >= 4) && (targetObject.minerals[0] < targetObject.minerals[1])) {
		let posX = targetObject.posX,
		posY = targetObject.posY,
		energy = targetObject.energy[0],
		minerals = targetObject.minerals[0];

		energy = decEnergy(energy, 4);
		minerals = incParam(targetObject.minerals, 1);
		worldEnergy -= 4; // поправка на прибавление энергии из decEnergy
		worldObj[posX][posY].energy[0] = energy;
		worldObj[posX][posY].minerals[0] = minerals;	
	}
}

// * Функция создания бота в определенных координатах
function createNewBot(coordX, coordY, ...[mode, parentGenom]) {
	let newBot = new Bot(coordX, coordY),
	mutationChance,
	genom = newBot['genom'];

	if (mode == 'randomGenom') {
		// console.log(genom);
		// genom.randomGenom();
		// console.log(genom);
		genom = randomGenomGenerator();
	} else if (mode == 'parentGenom') {
		genom = parentGenom;
	}

	mutationChance = getRandomInt(0, 100);
	if (mutationChance <= MUTATION_FACTOR) {
		genom = genomMutate(genom);
	}

	newBot['genom'] = genom;
	worldMatrix[coordX][coordY] = newBot;
}

// * Проверка - не пора ли родить нового бота?
function botCanMakeChild(botObject) {
	let ageLvl = checkOwnParamLvl(botObject, 'age'),
	energyLvl = checkOwnParamLvl(botObject);

	if (energyLvl >= 7 && ageLvl >=0) {
		return true;
	} else {
		return false;
	}
}

// * Бот создает нового бота
function botCreateChild(botObject, worldObj) {
	let parentX = botObject.posX,
	parentY = botObject.posY,
	newBotX,
	newBotY;

	for (let index = 15; index--; ) {
		let difX = getRandomInt(-1, 1),
		difY = getRandomInt(-1, 1);
		
		while ((difX == 0) && (difY == 0)) {
			difX = getRandomInt(-1, 1),
			difY = getRandomInt(-1, 1);
		}
	
		newBotX = parentX + difX;
		newBotY = parentY + difY;
	
		if ((newBotX > 0 && newBotX < WORLD_X) && (newBotY > 0 && newBotY < WORLD_Y)) {
			if (worldObj[newBotX][newBotY].objType == 'space') {
				let temp = Math.round(worldObj[parentX][parentY].energy[0] / 2);
				let parentGenom = worldObj[parentX][parentY].genom;
				createNewBot(newBotX, newBotY, 'parentGenom', parentGenom);
				worldObj[newBotX][newBotY].energy[0] = temp;
				worldObj[parentX][parentY].energy[0] = worldObj[parentX][parentY].energy[0] - temp;
				temp = Math.round(worldObj[parentX][parentY].minerals[0] / 2);
				worldObj[newBotX][newBotY].minerals[0] = temp;
				worldObj[parentX][parentY].minerals[0] = worldObj[parentX][parentY].minerals[0] - temp;
				index = 0;
			} else {
				continue;
			}		
		}
	}
}

// TODO: Check flags
// ToDo: Передаем объект и флаг, проверяем значение для поля "флаг" и если 1 - возвращаем true иначе false
function checkFlags(targetObject, targetFlag) {
	return false;
}

// TODO: Set hungry flag to
function setHungryFlag(params) {
	return false;
}

// * Сменить флаг объекта с жив на мертв
function revertAliveFlag(targetObject) {
	targetObject.flagAlive = 0;
	return false;
}

// TODO: Bot give resources in some direction
function giveResources(params) {
	return false;
}

// * Бот нападает на другого бота в определенном направлении
function botAttackBot(botObject, coordX, coordY, attackedFromDir) {
	if (worldMatrix[coordX][coordY].objType == 'bot') {
		let defBot = worldMatrix[coordX][coordY],
		defEnergy = defBot.energy[0],
		defMinerals = defBot.minerals[0],
		botHungry = botObject.flagHungry,
		botEnergy = botObject.energy[0],
		botMinerals = botObject.minerals[0],
		botEnergyDiff = botObject.energy[1] - botObject.energy[0],
		botMineralsDiff = botObject.energy[1] - botObject.energy[0],
		botPosX = botObject.posX,
		botPosY = botObject.posY,
		multiplier = 1,
		oneBiteValue = 100,
		temp;

		if (botHungry == 1) {
			multiplier = 2.5;
		}

		if ((defEnergy <= multiplier * oneBiteValue) && (botEnergyDiff <= defEnergy)) {
			temp = botEnergyDiff;
		} else if ((defEnergy <= multiplier * oneBiteValue) && (botEnergyDiff > defEnergy)) {
			temp = defEnergy;
		} else if ((defEnergy > multiplier * oneBiteValue) && (botEnergyDiff <= defEnergy)) {
			temp = botEnergyDiff; 
		} else if ((defEnergy > multiplier * oneBiteValue) && (botEnergyDiff > defEnergy)) {
			temp = oneBiteValue;
		}

		botEnergy += multiplier * temp;
		defEnergy -= multiplier * temp;

		if ((defMinerals <= multiplier * oneBiteValue) && (botMineralsDiff <= defMinerals)) {
			temp = botMineralsDiff;
		} else if ((defMinerals <= multiplier * oneBiteValue) && (botMineralsDiff > defMinerals)) {
			temp = defMinerals;
		} else if ((defMinerals > multiplier * oneBiteValue) && (botMineralsDiff <= defMinerals)) {
			temp = botMineralsDiff; 
		} else if ((defMinerals > multiplier * oneBiteValue) && (botMineralsDiff > defMinerals)) {
			temp = oneBiteValue;
		}

		botMinerals += multiplier * temp;
		defMinerals -= multiplier * temp;

		worldMatrix[coordX][coordY].energy[0] = defEnergy;
		worldMatrix[coordX][coordY].minerals[0] = defMinerals;
		worldMatrix[botPosX][botPosY].minerals[0] = botMinerals;

		defBot.flagAttacked[0] = attackedFromDir;

		if (defBot.energy[0] <= 0) {
			botToMeat(defBot);
		}
		return botEnergy; 
	}
}

// * Eat tree/meat/mineral 
function botEatFrontObject(botObject, coordX, coordY, type) {
	if (type == 'tree' || 'meat' || 'mineral') {
		if (worldMatrix[coordX][coordY].objType == type) {
			let targetObj = worldMatrix[coordX][coordY],
			objectEnergy = targetObj.energy[0],
			objectMinerals = targetObj.minerals[0],
			botHungry = botObject.flagHungry,
			botEnergy = botObject.energy[0],
			botMinerals = botObject.minerals[0],
			botEnergyDiff = botObject.energy[1] - botObject.energy[0],
			botMineralsDiff = botObject.energy[1] - botObject.energy[0],
			botPosX = botObject.posX,
			botPosY = botObject.posY,
			multiplier = 1,
			oneBiteValue = 80,
			temp;
	
			if (botHungry == 1) {
				multiplier = 2.5;
			}

			if (type == 'mineral') {
				oneBiteValue = 20;
			}
	
			if ((objectEnergy <= multiplier * oneBiteValue) && (botEnergyDiff <= objectEnergy)) {
				temp = botEnergyDiff;
			} else if ((objectEnergy <= multiplier * oneBiteValue) && (botEnergyDiff > objectEnergy)) {
				temp = objectEnergy;
			} else if ((objectEnergy > multiplier * oneBiteValue) && (botEnergyDiff <= objectEnergy)) {
				temp = botEnergyDiff; 
			} else if ((objectEnergy > multiplier * oneBiteValue) && (botEnergyDiff > objectEnergy)) {
				temp = oneBiteValue;
			}
	
			botEnergy += multiplier * temp;
			objectEnergy -= multiplier * temp;
	
			if (type == 'mineral') {
				oneBiteValue = 80;
			}

			if (type == 'tree' || type == 'meat') {
				oneBiteValue = 20;
			}

			if ((objectMinerals <= multiplier * oneBiteValue) && (botMineralsDiff <= objectMinerals)) {
				temp = botMineralsDiff;
			} else if ((objectMinerals <= multiplier * oneBiteValue) && (botMineralsDiff > objectMinerals)) {
				temp = objectMinerals;
			} else if ((objectMinerals > multiplier * oneBiteValue) && (botMineralsDiff <= objectMinerals)) {
				temp = botMineralsDiff; 
			} else if ((objectMinerals > multiplier * oneBiteValue) && (botMineralsDiff > objectMinerals)) {
				temp = oneBiteValue;
			}
	
			botMinerals += multiplier * temp;
			objectMinerals -= multiplier * temp;
	
			worldMatrix[coordX][coordY].energy[0] = objectEnergy;
			worldMatrix[coordX][coordY].minerals[0] = objectMinerals;
			worldMatrix[botPosX][botPosY].minerals[0] = botMinerals;
			return botEnergy; 
		}
	} else {
		return false;
	}
}

// * Бот проверяет свой уровень энергии
function checkOwnParamLvl(botObject, paramType = 'energy') {
	if (botObject[paramType] != undefined) {
		let param = botObject[paramType][0],
		maxParam = botObject[paramType][1],
		paramLvl = Math.floor(param / maxParam * 10);
		return paramLvl; // возвращаем уровень от 0 - 10
	} else {
		return false;
	}
}

// * Бот проверяет атакован ли он?
function botCheckFlagAttacked(botObject) {
	if (botObject != undefined) {
		let attacked = botObject.flagAttacked[0];
		return attacked; // возвращаем направление атаки в текущем ходу, 0 если не атакован
	} else {
		return false;
	}
}

// * Bot to meat
function botToMeat(botObject) {
	let x = botObject.posX,
	y = botObject.posY,
	energy = botObject.energy[0],
	minerals = botObject.minerals[0],
	meat = new Meat(x, y);

	meat.energy[0] = energy;
	meat.minerals[0] = minerals;
	worldMatrix[x][y] = meat;
}

// * Meat to mineral
function meatToMineral(meatObject, worldObj) {
	let x = meatObject.posX,
		y = meatObject.posY,
		energy = meatObject.energy[0],
		minerals = meatObject.minerals[0],
		mineralObj = new Mineral(x, y);

		mineralObj.energy[0] = energy;
		mineralObj.minerals[0] = minerals;

	worldObj[x][y] = mineralObj;
}

// TODO: Tree to mineral
function treeToMineral(treeObject, worldObj) {
	let x = treeObject.posX,
		y = treeObject.posY,
		energy = treeObject.energy[0],
		minerals = treeObject.minerals[0],
		mineralObj = new Mineral(x, y);

		mineralObj.energy[0] = energy;
		mineralObj.minerals[0] = minerals;

	worldObj[x][y] = mineralObj;
}


// TODO: Mineral to energy
function mineralToEnergy(mineralObject, worldObj) {
	let x = mineralObject.posX,
		y = mineralObject.posY,
		energy = mineralObject.energy[0],
		minerals = mineralObject.minerals[0],
		spaceObj = new Space(x, y);

	worldEnergy += energy + minerals * 4;
	
	worldObj[x][y] = spaceObj;
}

// * Проверяем возраст бота
function checkBotAge(botObject) {
	let age = botObject.age[0],
	maxAge = botObject.age[1];
	if (age >= maxAge) {
		botToMeat(botObject);
	}
}

// * Проверяем энергию бота
function checkBotMainParam(botObject, param = 'energy') {
	let p = botObject[param][0];
	if (p <= 0) {
		botToMeat(botObject);
	}
}

// * Set speed of bot
function setSpeed(botObject) {
	let e = botObject.energy[0],
	eMax = botObject.energy[1],
	m = botObject.minerals[0],
	mMax = botObject.minerals[1],
	speed;
	speed = Math.ceil((95 + powerOfTwo(m) * powerOfTwo(mMax)) / (5 + powerOfTwo(e))) + Math.round(powerOfTwo(m) / powerOfTwo(e)) + Math.floor(powerOfTwo(mMax) / powerOfTwo(eMax));
	return speed;
}

// * Проверяем количество различий между геномами ботов (проверка на родственность)
function isRelative(a, b) { //передаем геномы ботов
	let x = -1;
	const MAX_DIFF = 2;
	let diff = 0;
	if (a.length == b.length) {
		for (let i = 0; i < a.length; i++) {
			if (a[i] != b[i]) {
				diff++;
			}
			if (diff > MAX_DIFF) {
				x = 0;
				break;
			}
		}
		if (diff <= MAX_DIFF) {
			x = 1;
		}
	}
	return x; // -1 разного размера геномы, 0 не родственники, 1 родственники
}

let timerId = setTimeout(function tick() {
	console.clear();
	console.log(`*******`);
	console.log(`step ${worldTime}`);
	console.log(`e = ${worldEnergy} | fe = ${fullWorldEnergy}`);
	main(worldMatrix);
	render(worldMatrix);
	timerId = setTimeout(tick, 100); // (*)
	worldTime++;
	if (worldTime >= STEPS) {
		clearTimeout(timerId);
	}
}, 500); 