// Abre un chromium con ventana para que entres a Ronspot a mano, y al cerrarla te deja
// la cookie de sesión y un config.toml ya relleno con tu GUID, tu parking y tu coche.
// La contraseña y el token de recaptcha se censuran antes de tocar el disco.
import { chromium } from 'playwright'
import { appendFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { argv, env } from 'node:process'

const OUT = env.RONSPOT_CAPTURE_DIR ?? argv[2] ?? `${env.HOME}/.ronspot`
mkdirSync(OUT, { recursive: true })
const TRAFFIC = `${OUT}/traffic.jsonl`
const STATE = `${OUT}/session.json`
const CONFIG = `${OUT}/config.toml`

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

// Lo que hace falta para el config, recogido al vuelo mientras navegas.
const found = { guid: null, zone: null, vehicleType: null, vehicleFuel: null, parks: [] }

function learnFromRequest(body) {
  if (!body) return
  const params = new URLSearchParams(body)
  found.guid ??= params.get('CollegesGuID') || params.get('GuId')
  found.zone ??= params.get('car_park_id') || params.get('ZoneID')
}

function learnFromCalendar(payload) {
  const tags = payload?.TagsList
  if (tags?.VehicleType?.length) found.vehicleType ??= tags.VehicleType[0].id
  if (tags?.vehicleFuel?.length) found.vehicleFuel ??= tags.vehicleFuel[0].id
  for (const park of payload?.car_park ?? []) {
    if (!found.parks.some(p => p.id === park.id)) {
      found.parks.push({ id: park.id, name: park.CarParkName })
    }
  }
}

function writeConfig() {
  if (!found.guid || !found.zone) return false
  const otros = found.parks
    .filter(p => String(p.id) !== String(found.zone))
    .map(p => `# otro parking tuyo: zone_id = ${p.id}  # ${p.name}`)
  const elegido = found.parks.find(p => String(p.id) === String(found.zone))
  writeFileSync(CONFIG, `# Generado por tools/capture.mjs. Revísalo antes de usarlo.
[ronspot]
guid = "${found.guid}"
zone_id = ${found.zone}${elegido ? `  # ${elegido.name}` : ''}
vehicle_type_id = ${found.vehicleType ?? 2}
vehicle_fuel_id = ${found.vehicleFuel ?? 2}
${otros.join('\\n')}${otros.length ? '\\n' : ''}
[sniper]
weekdays = [1, 3]      # 0 = lunes. [1, 3] = martes y jueves
horizon_days = 14      # mídelo con --status; en mi zona son 14
giveup_time = "09:30"  # pasada esa hora el día en curso ya no sirve
local_tz = "Europe/Madrid"
resync_minutes = 30

[notify]               # console | slack | discord
kind = "console"

[notify.slack]
token = ""
channel = ""

[notify.discord]
webhook = ""

[paths]
session = "${STATE}"
state = "${OUT}/state.json"
`)
  return true
}

const browser = await chromium.launch({ headless: false, args: ['--window-size=1500,980'] })
const ctx = await browser.newContext({ viewport: null })

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
  learnFromRequest(req.postData())
  if (body?.trimStart().startsWith('{')) {
    try { learnFromCalendar(JSON.parse(body)) } catch { /* no era el calendario */ }
  }
  appendFileSync(TRAFFIC, JSON.stringify({
    i: ++n, t: new Date().toISOString(), method: req.method(), url, type,
    status: res.status(), ct, post: redact(req.postData()), body,
  }) + '\n')
})

const dump = setInterval(async () => {
  try { writeFileSync(STATE, JSON.stringify(await ctx.storageState(), null, 2)) } catch { /* cerrando */ }
}, 5000)

await (await ctx.newPage()).goto('https://my.ronspot.ie/')
console.log(`
  1. Entra con tu email y tu contraseña (no se guarda: se censura antes de escribir nada).
  2. Abre el calendario de tu parking y navega una semana o dos.
  3. Cierra la ventana.

  Al cerrar te dejo en ${OUT}:
    session.json  la cookie de sesión
    config.toml   tu GUID, tu parking y tu coche, ya rellenos
`)
await new Promise(resolve => browser.on('disconnected', resolve))
clearInterval(dump)

if (writeConfig()) {
  console.log(`\n  Listo. Revisa ${CONFIG} y ajusta weekdays y giveup_time a tu gusto.`)
} else {
  console.log(`
  No he podido sacar tu GUID ni tu parking: ¿llegaste a abrir el calendario?
  Vuelve a lanzarlo y navega por él antes de cerrar la ventana.`)
}
