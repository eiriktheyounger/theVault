// Resolve Tailwind config absolutely so it works from root or ui cwd
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const tailwindConfig = join(here, 'tailwind.config.js')

export default {
  plugins: {
    tailwindcss: { config: tailwindConfig },
    autoprefixer: {},
  },
}
