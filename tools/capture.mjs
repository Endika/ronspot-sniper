// Abre un chromium con ventana para que entres a Ronspot a mano y va anotando
// todo lo que habla el portal. La contraseña y el token de recaptcha se censuran
// antes de tocar el disco.
import { chromium } from 'playwright'
import { appendFileSync, writeFileSync, mkdirSync } from 'node:fs'

const OUT = process.env.RONSPOT_CAPTURE_DIR ?? `${process.env.HOME}/workspace/ronspot-sniper-notes/capture`
mkdirSync(OUT, { recursive: true })
const TRAFFIC = `${OUT}/traffic.jsonl`
const STATE = `${OUT}/storage-state.json`

const SECRET = /^(password|pwd|pass|new_?password|confirm_?password|g-recaptcha-response|recaptcha\w*)$/i

function redact(body) {
  if (!body) return null
  if (body.trimStart().startsWith('{')) {
    try {
      const o = JSON.parse(body)
      for (const k of Object.keys(o)) if (SECRET.test(k)) o[k] = '<REDACTED>'
      return JSON.stringify(o)
    } catch { /* cae al tratamiento de formulario */ }
  }
  return body.split('&').map(kv => {
    const [k, ...v] = kv.split('=')
    return SECRET.test(decodeURIComponent(k)) ? `${k}=<REDACTED>` : `${k}=${v.join('=')}`
  }).join('&')
}

const browser = await chromium.launch({ headless: false, args: ['--window-size=1500,980'] })
const ctx = await browser.newContext({ viewport: null, locale: 'es-ES' })

let n = 0
ctx.on('response', async res => {
  const req = res.request()
  const url = req.url()
  if (!url.includes('ronspot')) return
  const type = req.resourceType()
  if (['image', 'font', 'stylesheet', 'media', 'script'].includes(type)) return
  const ct = res.headers()['content-type'] ?? ''
  let body = null
  if (type !== 'document' && /json|text/.test(ct)) {
    try { body = (await res.text()).slice(0, 6000) } catch { /* cuerpo ya consumido */ }
  }
  appendFileSync(TRAFFIC, JSON.stringify({
    i: ++n, t: new Date().toISOString(), method: req.method(), url, type,
    status: res.status(), ct, post: redact(req.postData()), body,
  }) + '\n')
  console.log(`${String(n).padStart(3)} ${req.method().padEnd(4)} ${res.status()} ${type.padEnd(9)} ${url.slice(0, 110)}`)
})

const dump = setInterval(async () => {
  try { writeFileSync(STATE, JSON.stringify(await ctx.storageState(), null, 2)) } catch { /* contexto cerrándose */ }
}, 5000)

await (await ctx.newPage()).goto('https://my.ronspot.ie/')
console.log('\n=== Entra a mano, abre el calendario de parking y haz UNA reserva. Cierra la ventana al terminar. ===\n')
await new Promise(resolve => browser.on('disconnected', resolve))
clearInterval(dump)
