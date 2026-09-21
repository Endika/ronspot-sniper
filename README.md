# ronspot-sniper

Vigila el calendario de parking de Ronspot y coge plaza los martes y jueves en cuanto
alguien libera hueco. Corre en el Pi, un tic por minuto desde cron.

## Lo que hay que saber antes de tocar nada

**El calendario miente.** `Spotavailable` y `AvailableParkingBay` de
`POST /member/Claim_release` salen a 1 en días que están llenos y a 0 en días que sí se
pueden reservar. Reservar guiándose por ese campo devuelve `Success`, deja la petición en
cola, y Ronspot la rechaza minutos después mandándote una notificación al móvil.

**La señal buena es el desplegable del coche.** `GetAvalablevehicleTypeDayWise` devuelve
un `<option>` con tu matrícula solo cuando de verdad queda plaza para ti; si no, devuelve
`0`. Es lo único que decide, y está en `RonspotClient.bookable()`. Está medido, no
supuesto: la única reserva que cuajó fue la única con `<option>` presente.

**Confirmar no es opcional.** `claimSpot` responde `"In Process"` con un `QueueProcessId`.
La reserva solo es firme cuando `getPendingClaimStatus` devuelve `isClaimSuccessful: 1`
con su `SpotID` y su `ParkingBayNumber`.

**`isClaimPendingRequest: 1` no significa "tengo algo en cola"**, significa "este día no es
tuyo". Sale en fechas que no has pedido nunca.

## Uso

```sh
python3 -m ronspot_sniper --config ~/ronspot/config.toml            # un tic
python3 -m ronspot_sniper --config ~/ronspot/config.toml --dry-run  # sin reservar
python3 -m ronspot_sniper --config ~/ronspot/config.toml --status   # qué tengo y qué falta
```

Sin novedad no imprime nada ni escribe en Slack. Es deliberado: corre cada minuto.

## Re-sembrar la cookie

El login lleva reCAPTCHA v3, así que no se puede automatizar. Cuando la sesión caduque
llegará un aviso a Slack (uno solo). Entonces, desde WSL:

```sh
node tools/capture.mjs          # abre chromium, entras a mano, cierras la ventana
scp ~/workspace/ronspot-sniper-notes/capture/storage-state.json lab:ronspot/session.json
ssh lab 'chmod 600 ~/ronspot/session.json'
```

La contraseña y el token de recaptcha se censuran antes de tocar el disco.

## Cron en el Pi

```
* * * * * cd /home/pi/ronspot && flock -n /tmp/ronspot.lock /usr/bin/python3 -m ronspot_sniper --config /home/pi/ronspot/config.toml >> /home/pi/ronspot/sniper.log 2>&1
```

## Tests

```sh
.venv/bin/python -m pytest tests/ -q
```

Integración contra un Ronspot en memoria alimentado con respuestas reales del portal,
anonimizadas en `tests/fixtures/`.
