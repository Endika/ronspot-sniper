# ronspot-sniper

Vigila el calendario de [Ronspot](https://ronspotflexwork.com/) y te reserva plaza de
parking los días que elijas, en cuanto alguien libera hueco. Pensado para correr desde
cron en una Raspberry Pi: un tic por minuto, y silencio absoluto mientras no pasa nada.

No es un cliente oficial. Habla con el portal de empleado igual que lo hace tu navegador.

## Por qué no basta con mirar `Spotavailable`

Si vas a tocar esto, esto es lo que te ahorra la noche que me costó a mí:

- **Hay una ventana de reserva** (14 días en mi zona; mídela con `--status`). **Fuera de
  ella Ronspot marca todos los días como libres**, fines de semana incluidos, y no deja
  reservar ninguno. Fiarse de `Spotavailable` acaba en reservas rechazadas.
- **La señal que vale es `GetAvalablevehicleTypeDayWise`**: solo devuelve un `<option>`
  con tu matrícula cuando de verdad se puede reservar. Es `RonspotClient.bookable()`, y es
  lo único que decide si se dispara una reserva.
- **Reservar es asíncrono.** `claimSpot` responde `"In Process"`; la reserva solo es firme
  cuando `getPendingClaimStatus` devuelve `isClaimSuccessful: 1`.
- **`isClaimPendingRequest: 1` no significa "tengo algo en cola"**, significa "este día no
  es tuyo". Sale en fechas que no has pedido nunca.
- **El reloj de Ronspot va en Dublín**, no en tu país. Las fechas se calculan en su zona;
  la hora de corte, en la tuya (`local_tz`).

## Puesta en marcha

Necesitas Python 3.11+, Node 20+ y una cuenta de Ronspot.

```sh
git clone https://github.com/<tu-usuario>/ronspot-sniper && cd ronspot-sniper
python3 -m venv .venv && .venv/bin/pip install -e .
npm install
```

El login lleva reCAPTCHA v3, así que **no se puede automatizar**. Entras tú una vez:

```sh
node tools/capture.mjs ~/.ronspot
```

Se abre un Chromium. Entras con tu cuenta, abres el calendario de tu parking, navegas una
semana o dos, y cierras la ventana. Al cerrar te deja en `~/.ronspot`:

- `session.json` — la cookie de sesión
- `config.toml` — tu GUID, tu parking y tu coche, ya rellenos

Tu contraseña y el token de recaptcha se censuran antes de escribir nada en disco.

Ajusta `weekdays` y `giveup_time`, y comprueba que te ve bien:

```sh
.venv/bin/python -m ronspot_sniper --config ~/.ronspot/config.toml --status
```

## Uso

```sh
python -m ronspot_sniper --config ~/.ronspot/config.toml            # un tic
python -m ronspot_sniper --config ~/.ronspot/config.toml --dry-run  # sin reservar
python -m ronspot_sniper --config ~/.ronspot/config.toml --status   # qué tengo y qué falta
python -m ronspot_sniper --config ~/.ronspot/config.toml --report   # manda ese resumen
```

Sin novedad no imprime nada ni avisa. Es deliberado: corre cada minuto.

## Configuración

Ver [`config.example.toml`](config.example.toml). Lo que más se toca:

| Opción | Qué hace |
|---|---|
| `weekdays` | Qué días quieres. `0` = lunes; `[1, 3]` = martes y jueves |
| `horizon_days` | Hasta dónde deja reservar tu Ronspot |
| `giveup_time` | Pasada esa hora el día en curso deja de perseguirse. `""` lo desactiva |
| `local_tz` | Tu reloj, para esa hora de corte |
| `resync_minutes` | Cada cuánto repasa el horizonte entero y mantiene viva la cookie |

## Avisos: Slack, Discord o lo que escribas tú

El núcleo solo conoce un puerto, `Notifier.send(texto)`. Los adaptadores viven en
`ronspot_sniper/notify/` y se eligen desde el config:

```toml
[notify]
kind = "discord"

[notify.discord]
webhook = "https://discord.com/api/webhooks/..."
```

Vienen `console`, `slack` y `discord`. **Para añadir el tuyo** (Telegram, ntfy, correo…):

1. Crea `ronspot_sniper/notify/telegram.py` con una clase que tenga
   `from_options(options) -> Telegram | None` y `send(text) -> bool`.
2. Regístrala en `ADAPTADORES` dentro de `notify/__init__.py`.
3. Su sección del config es `[notify.telegram]`, y llega tal cual a `from_options`.

Si tu adaptador se queda sin los datos que necesita, `from_options` devuelve `None` y los
avisos caen a consola: un aviso mal configurado no debe impedirte cazar la plaza.

## Qué te llega

1. **Plaza cogida** — en el momento. Varias en el mismo minuto van en un solo mensaje.
2. **Sesión caducada** — una sola vez. Es el único aviso que la app de Ronspot no te da.
3. **Parte diario** — lo que tienes y lo que falta, si programas `--report`.
4. **Parado** — ese mismo parte cuando algo está roto, en vez de la lista.

## Cron

```
* * * * * cd ~/ronspot-sniper && flock -n /tmp/ronspot.lock .venv/bin/python -m ronspot_sniper --config ~/.ronspot/config.toml >> ~/.ronspot/sniper.log 2>&1
0 8 * * * cd ~/ronspot-sniper && flock -n /tmp/ronspot.lock .venv/bin/python -m ronspot_sniper --config ~/.ronspot/config.toml --report >> ~/.ronspot/sniper.log 2>&1
0 5 * * * [ -f ~/.ronspot/sniper.log ] && [ $(stat -c%s ~/.ronspot/sniper.log) -gt 1048576 ] && : > ~/.ronspot/sniper.log
```

El log está vacío mientras no pasa nada; la tercera línea lo corta si una caída larga de
Ronspot lo hace crecer.

## Cuánto molesta a Ronspot

Un tic solo pide las semanas con un día objetivo que aún no es tuyo. Si no falta ninguno,
**no hace ni una petición**.

| Situación | Peticiones por minuto |
|---|---|
| Todo reservado | 0 |
| Un día pendiente | 2 |
| Repaso, cada 30 min | 3 |

Ante un 429 o un 403 se aparta solo, con espera exponencial de 5 min a 2 h.

## Re-sembrar la cookie

Cuando la sesión caduque te llega un aviso (uno solo). Entonces:

```sh
node tools/capture.mjs ~/.ronspot
```

## Puertas de calidad

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest tests/ -q
```

Los tests van contra un Ronspot en memoria alimentado con respuestas reales del portal,
anonimizadas, en `tests/fixtures/`. Si despliegas en una máquina con otro Python, pasa la
suite también allí.

## Limitaciones

- El login no se puede automatizar (reCAPTCHA v3): la cookie se siembra a mano.
- Está probado contra una sola instalación de Ronspot. `horizon_days` y los ids de
  vehículo pueden no coincidir con los tuyos; `--status` y `--dry-run` te lo dicen.
- Que una reserva se acepte no depende solo de este script: si otro te gana la carrera,
  Ronspot la rechaza y lo reintenta en el tic siguiente.

## Licencia

MIT. Ver [LICENSE](LICENSE).
