# Sitio web de Katalis Partners

Sitio estático de Gómez Hernández Consulting S.A.S. (Katalis Partners). Vive en https://katalispartners.com.co.

No usa frameworks ni paso de compilación: HTML, CSS y JavaScript que el navegador lee tal cual. Dos programas cortos en Python arman las páginas y las cifras.

## Estructura

| Carpeta | Qué tiene |
|---|---|
| `contenido/` | El texto de cada página. **Aquí se edita.** |
| `scripts/construir_sitio.py` | Pone encabezado, pie, contacto y política de seguridad a cada página de `contenido/` y escribe el HTML final. |
| `scripts/actualizar_cifras.py` | Convierte el Excel de cifras en `datos/cifras.json`. |
| `datos/cifras.json` | Las cifras que lee el tablero. No se edita a mano. |
| `assets/` | Estilos, letras, Chart.js y el código del tablero. |
| `pruebas/verificar.mjs` | La prueba que debe dar 0 fallas antes de publicar. |

Los `.html` de la raíz y de `blog/` se generan: no se editan a mano.

## Cambiar un texto

1. Edite el archivo en `contenido/`.
2. `python scripts/construir_sitio.py`
3. `node pruebas/verificar.mjs` → debe decir `0 fallas`.
4. Commit y push a `main`. GitHub Pages publica en uno o dos minutos.

La agenda, el teléfono, los correos, LinkedIn, la dirección de la plataforma, el enlace de Hotmart y el vencimiento de `security.txt` están al inicio de `scripts/construir_sitio.py`. El mismo programa escribe `.well-known/security.txt`; `.nojekyll` hace que GitHub Pages sirva esa carpeta con punto.

## Actualizar las cifras

1. Ponga el Excel nuevo en `datos/fuente/Datos_graficos_economia_solidaria.xlsx` (esa carpeta no se sube a GitHub).
2. `python scripts/actualizar_cifras.py`
3. Revise las referencias de inflación al inicio del mismo programa.
4. `node pruebas/verificar.mjs` y publique.

## Arquitectura de datos

```
Reporte oficial (Supersolidaria, BanRep, Banca de las Oportunidades)
   → Excel de trabajo validado (solo en el equipo, no en GitHub)
   → scripts/actualizar_cifras.py  (copia, no recalcula)
   → datos/cifras.json             (público, con fuente por serie)
   → assets/js/cifras.js           (dibuja; cuentas simples como variaciones y días)
   → cifras.html
```

Los plazos del Decreto 769 de 2025 se calculan en el navegador desde la vigencia (9 de julio de 2025), así nunca quedan desactualizados.

## Tubería de datos (Katalis Cifras · Fase 0: Pulso macro)

Los datos llegan solos desde fuentes oficiales y pasan por 4 capas antes de llegar a la web. Las fuentes, sus URL y qué pasa si cambian están en `scripts/tuberia/FUENTES.md`.

```
Fuente oficial (SFC/datos.gov.co, Banco de la República, DANE)
   → datos/crudo/<fuente>/<AAAA-MM-DD>/  respuesta tal cual (nunca se edita)      extraer.py
   → datos/limpio/<fuente>.json          formato común, números convertidos      validar.py
   → datos/indicadores/<fuente>.json     cálculos listos                         calcular.py
   → datos/web/macro.json                lo único que lee la web                 empaquetar.py
   → scripts/construir_sitio.py          franja «Pulso macro» en las 11 páginas
datos/registro.jsonl: una línea por fuente y ejecución (URL, consulta, hora UTC, filas, sha256, resultado)
```

- **Correr a mano:** `python scripts/tuberia/correr.py`, después `python scripts/construir_sitio.py` y `node pruebas/verificar.mjs`. Solo usa la librería estándar de Python y no necesita claves.
- **Pruebas de los validadores:** `python -m unittest discover -s pruebas -p "test_*.py"`.
- **Si una fuente falla:** no avanza, las demás siguen y la web conserva su último valor bueno. Si un dato pasa del plazo (TRM 7 días; tasa del Emisor 45 días sin consulta exitosa; IPC 45 días desde su publicación), la franja lo marca como «desactualizado».
- **Saltos anómalos** (`scripts/tuberia/saltos.py`): cada valor nuevo se compara con el último valor bueno publicado. Si salta más de lo normal, **no se publica solo**:
  - TRM: más de ±5 % frente al último valor;
  - tasa del Emisor: un cambio que no sea múltiplo de 0,25 puntos, o de más de 1 punto;
  - inflación anual: más de 1,5 puntos frente al último mes publicado;
  - historia: si la fuente cambia un valor ya publicado de un periodo pasado;
  - cartera SFC: más de ±10 % frente al corte anterior (entra con la Fase 1, cuando se publique).
- **Automático:** `.github/workflows/datos.yml` corre todos los días a las 6:17 a. m. de Bogotá (11:17 UTC) y también a mano (`workflow_dispatch`). Tiene 5 jobs:
  - `procesar` (solo lectura): extrae, valida, calcula, revisa saltos, construye y verifica el sitio, y guarda el resultado como artifact. Es el único que instala algo (Playwright) y no tiene credencial de escritura.
  - `publicar` (solo en `main`): no instala nada ni corre código del repositorio. Baja el artifact, copia solo `datos/`, las páginas `.html` y `sitemap.xml`, y hace commit «datos: corte AAAA-MM-DD» y push. Es el único job con permiso de escribir en el repositorio, junto con el siguiente.
  - `aprobar-anomalias` (solo en `main` y solo si hubo un salto): espera la aprobación de Andrés y publica la variante con el salto, que ya se construyó y verificó en `procesar`.
  - `avisar` (solo en `main`): abre o comenta un issue por cada fuente que falló («Falla en la tubería: <fuente>») y por cada salto («Revisar: salto anómalo en <fuente>»).
  - `cierre`: termina en rojo si una fuente o un job falló.
  - Lanzado a mano desde otra rama (modo prueba): solo `procesar` y `cierre`; no hace commit ni abre issues.
- **CI de los PR:** `.github/workflows/pruebas.yml` corre las pruebas unitarias y `verificar.mjs` en cada PR a `main`, con permiso de solo lectura y sin consultar las fuentes.
- **Cómo llega el aviso de una falla:** hoy los issues del repositorio están desactivados; si se activan o no, lo decide Andrés. Mientras sigan así:
  - el aviso es el **correo que GitHub manda cuando una ejecución termina en rojo**. La tubería termina en rojo si una fuente falla o si una prueba no pasa;
  - el intento de abrir el issue queda como advertencia dentro de la ejecución;
  - el detalle está en el resumen de la ejecución y en su artifact `diagnostico`.

  Si se activan los issues, el mismo workflow empieza a abrirlos sin cambiar nada.

### Aprobar un salto anómalo

Cuando hay un salto, la ejecución publica todo lo demás y deja el job `aprobar-anomalias` esperando. La web conserva el último valor bueno de esa fuente hasta que Andrés decida. GitHub le manda un correo a Andrés («review pending»).

1. Abra la ejecución (enlace del correo, o *Actions → datos*). Arriba aparece «Review pending deployments».
2. Lea en el resumen de la ejecución el motivo del salto (sección «Tubería de datos», línea «salto anómalo retenido»). Compárelo con la fuente oficial.
3. Clic en **Review deployments**, marque `datos-anomalos` y elija:
   - **Approve and deploy**: publica el dato nuevo. El commit dice «datos: corte AAAA-MM-DD (salto anómalo aprobado por Andrés: <fuente>)» y `registro.jsonl` lo anota.
   - **Reject**: no publica nada; la web sigue con el último valor bueno. Al día siguiente la tubería vuelve a evaluar.
4. Si no decide, la espera vence a los 30 días. Si mientras tanto `main` cambió (otra corrida o un PR), la aprobación ya no publica: el job se detiene y la corrida siguiente vuelve a evaluar sobre los datos nuevos.

**Probar la puerta sin esperar un salto real:** *Actions → datos → Run workflow* en `main`, con «probar_aprobacion» marcado. La TRM se trata como salto (el dato es el real), y así se ve la pantalla de aprobación. Las capturas de esa pantalla se agregan aquí después de la primera prueba en `main` (antes de fusionar no se puede: el workflow solo se lanza desde `main`).

El environment `datos-anomalos` está en *Settings → Environments*: revisor requerido andrezgmz, solo para la rama `main`. Si se borra, GitHub lo vuelve a crear **sin** revisor la próxima vez que el job lo nombre; no lo borre.

- **Capa cruda sin duplicados:** se guarda una carpeta nueva en `datos/crudo/<fuente>/<fecha>/` solo si la respuesta cambió (otro `sha256`). Si es igual, solo se anota «sin cambios» en `registro.jsonl`. Nunca se sobrescribe: un segundo cambio el mismo día va a `<fecha>-2`.
- **Excel en git:** ningún `.xlsx` fuera de `datos/crudo/`. Ahí solo van respuestas públicas tal cual, como el anexo del IPC del DANE. El Excel privado de `datos/fuente/` sigue ignorado. `pruebas/verificar.mjs` revisa las dos cosas.
- **Pendiente para la Fase 1:** pasar la tasa del Emisor al servicio SDMX documentado del Banco de la República (versión nueva) y dejar el servicio interno de suameca solo como respaldo si SDMX falla 3 días seguidos.

**Ojo con la protección de `main`:** el robot es la única excepción a «nadie empuja a `main`»: hace push directo con el `GITHUB_TOKEN`, y solo desde los jobs `publicar` y `aprobar-anomalias`. Hoy se puede porque la protección solo bloquea `--force` y el borrado. Si después se exigen PR o revisiones en `main`, el robot necesitará una de dos cosas:
- una excepción para GitHub Actions en la regla de protección;
- o cambiar el paso «Publicar» para que abra un PR con auto-merge, que hoy está apagado en el repositorio.

## Seguridad

Ver `SECURITY.md`.
