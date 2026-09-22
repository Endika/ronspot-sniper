# Seguridad

## Qué guarda este programa

- **La cookie de sesión de Ronspot**, en `session.json`. Es equivalente a estar dentro de
  tu cuenta: quien la tenga puede ver y cambiar tus reservas. Se escribe con permisos
  `600` y **nunca** debe entrar en git.
- **El token de Slack o el webhook de Discord**, en `config.toml`. Mismo trato.
- `config.toml`, `session.json` y `state.json` están en `.gitignore`. Compruébalo con
  `git status` antes de tu primer commit.

Tu contraseña **no se guarda en ningún momento**: `tools/capture.mjs` la censura, junto al
token de reCAPTCHA, antes de escribir nada en disco.

## Los fixtures de los tests

`tests/fixtures/` son respuestas reales del portal, anonimizadas: GUID a ceros, matrícula
`TESTPLATE`, nombres y correos sustituidos, identificadores de zona cambiados. Si añades
fixtures nuevos, pásales la misma tijera antes de commitear.

## Reportar un fallo de seguridad

Abre un *security advisory* privado en la pestaña Security del repositorio. No abras un
issue público con detalles explotables.

Este proyecto habla con un servicio de terceros con tus credenciales. Si encuentras algo
que afecte a Ronspot y no a este código, repórtalo a ellos directamente.
