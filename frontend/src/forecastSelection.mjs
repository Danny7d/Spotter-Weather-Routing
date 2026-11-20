export function selectedForecastTime(departureUtc, offsetHours) {
  return new Date(new Date(departureUtc).getTime() + offsetHours * 3_600_000)
}

export function forecastHourFromInput(event) {
  return Number(event.currentTarget.value)
}

export function selectedForecastLabel(departureUtc, offsetHours) {
  return selectedForecastTime(departureUtc, offsetHours)
    .toUTCString()
    .replace(/^(\w+),\s(\d+)\s(\w+)\s(\d+)\s(\d+:\d+).*$/, '$1 $2 $3 · $5') + ' UTC'
}

export function selectedForecastAt(point, offsetHours) {
  return point?.hours?.find((sample) => sample.offset_hours === offsetHours) ?? null
}

export function checkpointForecast(checkpoint, points, offsetHours) {
  const point = points?.find((item) =>
    item.latitude.toFixed(4) === checkpoint.latitude.toFixed(4) &&
    item.longitude.toFixed(4) === checkpoint.longitude.toFixed(4))
  const sample = selectedForecastAt(point, offsetHours)
  return sample && sample.risk_level !== 'unknown' ? sample : null
}
