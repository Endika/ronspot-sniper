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

**Hora de corte.** Pasada `giveup_time` (09:30, hora de Madrid) el día en curso deja de
perseguirse: a esa hora ya estás en la oficina con el coche aparcado en la calle y la
plaza no te sirve. Las fechas se calculan en la zona de Ronspot (Dublín) pero el corte va
en la tuya. Se desactiva poniendo `giveup_time = ""`.

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
0 5 * * * [ -f /home/pi/ronspot/sniper.log ] && [ $(stat -c%s /home/pi/ronspot/sniper.log) -gt 1048576 ] && : > /home/pi/ronspot/sniper.log
```

El log está vacío mientras no pasa nada. La segunda línea lo vacía si pasa de 1 MB: una
caída larga de Ronspot escribe un aviso por minuto y esto corre sobre una SD.

## Cuánto molesta a Ronspot

Un tic solo pide las semanas que contienen un martes o jueves que aún no es tuyo. Si no
falta ninguno, **el tic no hace ni una petición**. El coste real:

| Situación | Peticiones por minuto |
|---|---|
| Todo reservado | 0 |
| Un día pendiente | 1 semana + 1 comprobación de coche |
| Barrido (cada 30 min) | 3 semanas |

El barrido no es solo para detectar una cancelación ajena: es lo que mantiene viva la
cookie de sesión cuando no hay nada que cazar.

## Puertas de calidad

Las tres tienen que estar en verde antes de tocar el Pi:

```sh
.venv/bin/ruff check .        # lint
.venv/bin/ruff format --check .
.venv/bin/mypy                # strict
.venv/bin/python -m pytest tests/ -q
```

Y la suite también sobre el intérprete de producción, que no es el mismo:

```sh
rsync -a tests/ ronspot_sniper/ pyproject.toml lab:ronspot/
ssh lab 'cd ~/ronspot && .venv-test/bin/python -m pytest tests/ -q'
```

Integración contra un Ronspot en memoria alimentado con respuestas reales del portal,
anonimizadas en `tests/fixtures/`.
