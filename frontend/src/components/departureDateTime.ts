export type Meridiem = 'AM' | 'PM'

/** Build the naive local datetime string expected by the API from 12-hour fields. */
export function toNaiveLocalDateTime(
  date: string,
  hour: string,
  minute: string,
  meridiem: Meridiem,
): string | null {
  const hourNumber = Number(hour)
  const minuteNumber = Number(minute)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isInteger(hourNumber) || hourNumber < 1 || hourNumber > 12 ||
      !/^\d{1,2}$/.test(minute) || !Number.isInteger(minuteNumber) || minuteNumber < 0 || minuteNumber > 59) {
    return null
  }

  const [year, month, day] = date.split('-').map(Number)
  const calendarDate = new Date(year, month - 1, day)
  if (calendarDate.getFullYear() !== year || calendarDate.getMonth() !== month - 1 || calendarDate.getDate() !== day) {
    return null
  }

  const hour24 = (hourNumber % 12) + (meridiem === 'PM' ? 12 : 0)
  return `${date}T${String(hour24).padStart(2, '0')}:${String(minuteNumber).padStart(2, '0')}`
}

export function isFutureDeparture(departureLocal: string, now = new Date()): boolean {
  const departure = new Date(departureLocal)
  return !Number.isNaN(departure.getTime()) && departure.getTime() > now.getTime()
}
