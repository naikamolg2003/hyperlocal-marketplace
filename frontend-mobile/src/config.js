import { Platform } from 'react-native';

// In Android emulator, 10.0.2.2 points to host machine localhost.
// In iOS Simulator and Web, localhost points to the local machine.
export const DEFAULT_API_URL = Platform.select({
  android: 'http://10.0.2.2:8000',
  default: 'http://localhost:8000',
});

export const PRESET_LOCATIONS = [
  {
    id: 'wakad',
    name: 'Wakad, Pune',
    latitude: 18.5987,
    longitude: 73.7660,
    subtitle: 'Datta Mandir Rd, Pune, MH',
  },
  {
    id: 'indiranagar',
    name: 'Indiranagar, Blr',
    latitude: 12.9784,
    longitude: 77.6408,
    subtitle: '100ft Road, Bangalore, KA',
  },
  {
    id: 'custom',
    name: 'Custom GPS',
    latitude: 18.5987,
    longitude: 73.7660,
    subtitle: 'Manual Latitude & Longitude',
  },
];
