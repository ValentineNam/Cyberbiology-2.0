function getRandomInt(min, max) {
  if (min < max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  } else {
    return Math.floor(Math.random() * (min - max + 1)) + max;
  }
}

function create2DArray(rows, cols) {
  return Array.from({ length: rows }, () => Array(cols).fill(null));
}

function getFrontCellCoordinates(direction, x, y, worldWidth, worldHeight) {
  let newX = x;
  let newY = y;

  switch (direction) {
    case 1: // верх
      if (y > 0) newY = y - 1; else return null;
      break;
    case 2: // верх-право
      if (x < worldWidth - 1 && y > 0) { newX = x + 1; newY = y - 1; } else return null;
      break;
    case 3: // право
      if (x < worldWidth - 1) newX = x + 1; else return null;
      break;
    case 4: // право-низ
      if (x < worldWidth - 1 && y < worldHeight - 1) { newX = x + 1; newY = y + 1; } else return null;
      break;
    case 5: // низ
      if (y < worldHeight - 1) newY = y + 1; else return null;
      break;
    case 6: // лево-низ
      if (x > 0 && y < worldHeight - 1) { newX = x - 1; newY = y + 1; } else return null;
      break;
    case 7: // лево
      if (x > 0) newX = x - 1; else return null;
      break;
    case 8: // лево-верх
      if (x > 0 && y > 0) { newX = x - 1; newY = y - 1; } else return null;
      break;
    default:
      return null;
  }

  return [newX, newY];
}

module.exports = {
  getRandomInt,
  create2DArray,
  getFrontCellCoordinates
};