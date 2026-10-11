'use strict'
/* Облегченная версия моделей */
/* Рисуем дерево */
function drawTree(ctx, x, y, s, color) {
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.moveTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (0.5 + y) * s, (2.5 + x) * s, (0.5 + y) * s);
	ctx.lineTo((7.5 + x) * s, (0.5 + y) * s);
	ctx.quadraticCurveTo((9.5 + x) * s, (0.5 + y) * s, (9.5 + x) * s, (2.5 + y) * s);
	ctx.lineTo((9.5 + x) * s, (7.5 + y) * s);
	ctx.quadraticCurveTo((9.5 + x) * s, (9.5 + y) * s, (7.5 + x) * s, (9.5 + y) * s);
	ctx.lineTo((2.5 + x) * s, (9.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (9.5 + y) * s, (0.5 + x) * s, (7.5 + y) * s);
	ctx.lineTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.fill();
	/* Добавим немного объема за счет "света" слева-наверху */
	ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
	ctx.beginPath();
	ctx.moveTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (0.5 + y) * s, (2.5 + x) * s, (0.5 + y) * s);
	ctx.quadraticCurveTo((6 + x) * s, (0.5 + y) * s, (6 + x) * s, (4 + y) * s);
	ctx.quadraticCurveTo((6 + x) * s, (6 + y) * s, (4 + x) * s, (6 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (6 + y) * s, (0.5 + x) * s, (2.5 + y) * s);
	ctx.fill();
}

/* Рисуем куст */
function drawBush(ctx, x, y, s, color) {
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.moveTo((2 + x) * s, (4 + y) * s);
	ctx.quadraticCurveTo((2+x)*s, (2+y)*s, (4+x)*s, (2+y)*s);
	ctx.lineTo((6 + x) * s, (2 + y) * s);
	ctx.quadraticCurveTo((8+x)*s, (2+y)*s, (8+x)*s, (4+y)*s);
	ctx.lineTo((8 + x) * s, (6 + y) * s);
	ctx.quadraticCurveTo((8+x)*s, (8+y)*s, (6+x)*s, (8+y)*s);
	ctx.lineTo((4 + x) * s, (8 + y) * s);
	ctx.quadraticCurveTo((2+x)*s, (8+y)*s, (2+x)*s, (6+y)*s);
	ctx.fill();
	/* Добавим немного объема за счет "света" слева-наверху */
	ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
	ctx.beginPath();
	ctx.moveTo((2 + x) * s, (4 + y) * s);
	ctx.quadraticCurveTo((2+x)*s, (2+y)*s, (4+x)*s, (2+y)*s);
	ctx.quadraticCurveTo((6+x)*s, (2+y)*s, (6+x)*s, (4+y)*s);
	ctx.quadraticCurveTo((6+x)*s, (6+y)*s, (4+x)*s, (6+y)*s);
	ctx.quadraticCurveTo((2+x)*s, (6+y)*s, (2+x)*s, (4+y)*s);
	ctx.fill();
}

/* Рисуем траву */
function drawGrass(ctx, x, y, s, color) {
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.arc((3 + x) * s, (3 + y) * s, 2.5, 0, 2*Math.PI);
	ctx.fill();
	ctx.beginPath();
	ctx.arc((3 + x) * s, (7.5 + y) * s, 2.5, 0, 2*Math.PI);
	ctx.fill();
	ctx.beginPath();
	ctx.arc((7.5 + x) * s, (7.5 + y) * s, 2.5, 0, 2*Math.PI);
	ctx.fill();
	ctx.beginPath();
	ctx.arc((7.5 + x) * s, (3 + y) * s, 2.5, 0, 2*Math.PI);
	ctx.fill();
}

/* Рисуем бота */
function drawBot(ctx, x, y, s, color = 'gray') {
	/* Тело бота */
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.moveTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (0.5 + y) * s, (2.5 + x) * s, (0.5 + y) * s);
	ctx.lineTo((7.5 + x) * s, (0.5 + y) * s);
	ctx.quadraticCurveTo((9.5 + x) * s, (0.5 + y) * s, (9.5 + x) * s, (2.5 + y) * s);
	ctx.lineTo((9.5 + x) * s, (7.5 + y) * s);
	ctx.quadraticCurveTo((9.5 + x) * s, (9.5 + y) * s, (7.5 + x) * s, (9.5 + y) * s);
	ctx.lineTo((2.5 + x) * s, (9.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (9.5 + y) * s, (0.5 + x) * s, (7.5 + y) * s);
	ctx.lineTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.fill();
	/* Рисуем глаза */
	ctx.fillStyle = 'white';
	ctx.beginPath();
	ctx.arc((4.125+x)*s, (4.25+y)*s, s/1.5, 0, Math.PI*2, true);
	ctx.fill();
	ctx.beginPath();
	ctx.arc((5.875+x)*s, (4.25+y)*s, s/1.5, 0, Math.PI*2, true);
	ctx.fill();
	/* Рисуем зрачки */
	ctx.fillStyle = 'black';
	ctx.beginPath();
	ctx.arc((4.125+x)*s, (4+y)*s, s/3, 0, Math.PI*2, true);
	ctx.fill();
	ctx.beginPath();
	ctx.arc((5.875+x)*s, (4+y)*s, s/3, 0, Math.PI*2, true);
	ctx.fill();
}

/* Рисуем минерал */
function drawMineral(ctx, x, y, s, color = 'gray') {
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.moveTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (0.5 + y) * s, (2.5 + x) * s, (0.5 + y) * s);
	ctx.lineTo((7.5 + x) * s, (0.5 + y) * s);
	ctx.quadraticCurveTo((9.5 + x) * s, (0.5 + y) * s, (9.5 + x) * s, (2.5 + y) * s);
	ctx.lineTo((9.5 + x) * s, (7.5 + y) * s);
	ctx.quadraticCurveTo((9.5 + x) * s, (9.5 + y) * s, (7.5 + x) * s, (9.5 + y) * s);
	ctx.lineTo((2.5 + x) * s, (9.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (9.5 + y) * s, (0.5 + x) * s, (7.5 + y) * s);
	ctx.lineTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.fill();
	/* Добавим немного объема за счет "света" слева-наверху */
	ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
	ctx.beginPath();
	ctx.moveTo((0.5 + x) * s, (2.5 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (0.5 + y) * s, (2.5 + x) * s, (0.5 + y) * s);
	ctx.quadraticCurveTo((6 + x) * s, (0.5 + y) * s, (6 + x) * s, (4 + y) * s);
	ctx.quadraticCurveTo((6 + x) * s, (6 + y) * s, (4 + x) * s, (6 + y) * s);
	ctx.quadraticCurveTo((0.5 + x) * s, (6 + y) * s, (0.5 + x) * s, (2.5 + y) * s);
	ctx.fill();
}

export { drawTree, drawBush, drawGrass, drawBot, drawMineral };