# ronspot-sniper

Vigila el calendario de parking de Ronspot y coge plaza los martes y jueves en cuanto
alguien libera hueco. Corre en el Pi, un tic por minuto desde cron.

## Lo que hay que saber antes de tocar nada

**La ventana de reserva es de 14 días.** Medido el 2026-09-22: el último día reservable
era hoy+13 y a partir de hoy+14 no se puede reservar nada. Mirar más lejos solo gasta
peticiones, y es la trampa que explica todo lo demás.

**Fuera de plazo, Ronspot marca todos los días como libres.** `Spotavailable` y
`AvailableParkingBay` valen 1 en cada día futuro fuera de ventana, fines de semana
incluidos. Reservar guiándose por ese campo devuelve `Success`, deja la petición en cola y
Ronspot la rechaza minutos después mandando una notificación al móvil.

**La puerta es `RonspotClient.bookable()`**, que consulta
`GetAvalablevehicleTypeDayWise`: devuelve un `<option>` con la matrícula solo cuando de
verdad se puede reservar ese día. En la muestra medida coincide siempre con el inverso de
`Spotavailable`, así que no es información independiente — pero es la polaridad que
concuerda con la realidad, y es la única que se usa para decidir.

**Confirmar no es opcional.** `claimSpot` responde `"In Process"` con un `QueueProcessId`.
La reserva solo es firme cuando `getPendingClaimStatus` devuelve `isClaimSuccessful: 1`
con su `SpotID` y su `ParkingBayNumber`.

**`isClaimPendingRequest: 1` no significa "tengo algo en cola"**, significa "este día no es
tuyo". Sale en fechas que no has pedido nunca.

**Un rechazo no descarta el día.** Suele significar que otro ha ganado la carrera por
segundos, así que el script vuelve a intentarlo en el tic siguiente, siempre.

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
