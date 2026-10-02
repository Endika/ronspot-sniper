# Changelog

## [0.2.6](https://github.com/Endika/ronspot-sniper/compare/v0.2.5...v0.2.6) (2026-10-02)


### Bug Fixes

* use pass in protocol bodies so CodeQL stops flagging them ([044863a](https://github.com/Endika/ronspot-sniper/commit/044863a2242fc2d13a48479c79e7761c317b5540))

## [0.2.5](https://github.com/Endika/ronspot-sniper/compare/v0.2.4...v0.2.5) (2026-09-29)


### Bug Fixes

* **capture:** close the browser when its last window closes ([52cd44e](https://github.com/Endika/ronspot-sniper/commit/52cd44e9b7ae9f5ac16aacc61b158c9b2edca19d))

## [0.2.4](https://github.com/Endika/ronspot-sniper/compare/v0.2.3...v0.2.4) (2026-09-29)


### Bug Fixes

* keep the session cookie Ronspot rotates so it stops expiring daily ([24126c8](https://github.com/Endika/ronspot-sniper/commit/24126c85608054d3e2cd51ae109b2fd697abe6b8))

## [0.2.3](https://github.com/Endika/ronspot-sniper/compare/v0.2.2...v0.2.3) (2026-09-27)


### Bug Fixes

* treat a 401 as an expired session so the alert goes out ([f9fcc8a](https://github.com/Endika/ronspot-sniper/commit/f9fcc8a7e0023230b4ea40fff75caa5555fb70e3))

## [0.2.2](https://github.com/Endika/ronspot-sniper/compare/v0.2.1...v0.2.2) (2026-09-27)


### Documentation

* correct the session file mode, status codes and commit language, and list traffic.jsonl ([d23beea](https://github.com/Endika/ronspot-sniper/commit/d23beeaa31ab6473883840be1f26d2fa324f0475))

## [0.2.1](https://github.com/Endika/ronspot-sniper/compare/v0.2.0...v0.2.1) (2026-09-25)


### Bug Fixes

* stop chasing Dublin's today once it is already tomorrow in Madrid ([323096d](https://github.com/Endika/ronspot-sniper/commit/323096d8519bdc1f93838b5e2a3c847f4376c185))

## [0.2.0](https://github.com/Endika/ronspot-sniper/compare/v0.1.0...v0.2.0) (2026-09-23)


### Features

* abandonar el dia en curso pasada la hora de corte ([fae015c](https://github.com/Endika/ronspot-sniper/commit/fae015c327c1fad67e0a4b825a71d452418f61d7))
* avisos como adaptadores intercambiables y puesta en marcha para terceros ([124987f](https://github.com/Endika/ronspot-sniper/commit/124987f71d801539b7465ad18ae380e955386d93))
* cazador de plazas de parking en Ronspot para martes y jueves ([15611f0](https://github.com/Endika/ronspot-sniper/commit/15611f002b046632db9fae15f3d4b50670c0c769))
* parte diario por slack para el caso en que no se pilla nada ([34bac67](https://github.com/Endika/ronspot-sniper/commit/34bac673915c47d0d9139c6c9ccba81831023e26))


### Bug Fixes

* corregir los diez defectos del verificador adversario ([d12514f](https://github.com/Endika/ronspot-sniper/commit/d12514f11c2222cb92ea090f420071e3da1b4afc))
* limitar el cazador a la ventana real de 14 dias y reintentar siempre tras un rechazo ([f46a69c](https://github.com/Endika/ronspot-sniper/commit/f46a69c52cf9e0f75a84e6d1df58c88c96f2c8de))
* make the 8am report wait for the lock instead of losing it to the tick ([ec6d1b5](https://github.com/Endika/ronspot-sniper/commit/ec6d1b5f0075b09807080fdcf182fdeb439f404a))
* tratar la caida de red de las 4:00 como condicion esperada y no como error ([a3bc338](https://github.com/Endika/ronspot-sniper/commit/a3bc338677a3b048fd63b9da31e02c97d6e96013))


### Documentation

* documentar el adaptador de slack junto al de discord ([99b208c](https://github.com/Endika/ronspot-sniper/commit/99b208cc46a776ec3d8cf888a711408411666f6d))
* quitar el security.md que pisaba la politica por defecto del perfil ([f65b170](https://github.com/Endika/ronspot-sniper/commit/f65b1700a808ada74320129c6461d414be21897a))
* readme en ingles para que el proyecto se encuentre ([bd9bec6](https://github.com/Endika/ronspot-sniper/commit/bd9bec6c12b5db8c0537c292f7610db671b395c4))
