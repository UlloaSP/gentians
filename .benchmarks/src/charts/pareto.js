export function paretoFrontier(points) {
  let best = -Infinity;
  return [...points]
    .sort((left, right) => left.value[0] - right.value[0] || right.value[1] - left.value[1])
    .filter((point) => {
      if (point.value[1] <= best) return false;
      best = point.value[1];
      return true;
    });
}
