// Bazowy adres API. W dev pusty (Vite proxy przekazuje /api do backendu),
// na produkcji ustaw VITE_API_URL na adres wdrożonego backendu.
export const API_URL: string = import.meta.env.VITE_API_URL ?? ''
