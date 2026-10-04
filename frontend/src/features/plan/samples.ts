import { emptyForm, type TripForm } from '../../state/urlState'

export interface SampleTrip {
  title: string
  /** What the sample shows off, in a few words. */
  shows: string
  form: TripForm
}

// Made-up log header details, so a sample's sheets come out fully filled in.
const SAMPLE_HEADER = {
  driver: 'J. Doe',
  carrier: 'Sample Carrier Inc.',
  truck: '1042',
  trailer: '53-117',
  shipper: 'Sample Shipper',
  commodity: 'General freight',
  load_id: 'LD-1042',
  home_terminal: '',
}

function sample(
  title: string,
  shows: string,
  places: [string, number, number][],
  cycleUsedHours: number,
  homeTerminal: string,
): SampleTrip {
  const [current, pickup, dropoff] = places.map(([label, lat, lon]) => ({ label, lat, lon }))
  return {
    title,
    shows,
    form: {
      ...emptyForm(),
      current,
      pickup,
      dropoff,
      cycleUsedHours: String(cycleUsedHours),
      header: { ...SAMPLE_HEADER, home_terminal: homeTerminal },
    },
  }
}

/**
 * Tomorrow at 07:00, as the form writes it: a sample starts there, so the days and
 * stops on its card come out the same whatever the time it is tried.
 */
export function sampleStart(now = new Date()): string {
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}T07:00`
}

/** Trips to try from the empty map: picked places, so they plan without a search. */
export const SAMPLE_TRIPS: SampleTrip[] = [
  sample(
    'Los Angeles → Phoenix → Atlanta',
    '52 h used · 34-hour restart · 5 days',
    [
      ['Los Angeles, CA', 34.05369, -118.24277],
      ['Phoenix, AZ', 33.44844, -112.07414],
      ['Atlanta, GA', 33.75447, -84.38982],
    ],
    52,
    'Los Angeles, CA',
  ),
  sample(
    'Chicago → Indianapolis → Denver',
    '20 h used · 10-hour rests · 3 days',
    [
      ['Chicago, IL', 41.87556, -87.62442],
      ['Indianapolis, IN', 39.76833, -86.15835],
      ['Denver, CO', 39.73924, -104.98486],
    ],
    20,
    'Chicago, IL',
  ),
  sample(
    'Dallas → Fort Worth → Houston',
    '8 h used · one day',
    [
      ['Dallas, TX', 32.77627, -96.79686],
      ['Fort Worth, TX', 32.75318, -97.33275],
      ['Houston, TX', 29.75894, -95.3677],
    ],
    8,
    'Dallas, TX',
  ),
]
