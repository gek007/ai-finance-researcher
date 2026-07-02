type ClientEnv = {
  apiBaseUrl: string
  supabaseUrl: string
  supabaseAnonKey: string
}

function readRequiredEnv(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name]
  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Missing required environment variable: ${name}`)
  }
  return value
}

export const env: ClientEnv = {
  apiBaseUrl: readRequiredEnv('VITE_API_BASE_URL'),
  supabaseUrl: readRequiredEnv('VITE_SUPABASE_URL'),
  supabaseAnonKey: readRequiredEnv('VITE_SUPABASE_ANON_KEY'),
}
