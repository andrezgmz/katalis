"""Control de saltos anómalos: compara lo nuevo con el último valor bueno publicado.

Las validaciones de rango (validar.py) detienen datos absurdos; este control detiene
un dato verosímil pero raro. Un salto anómalo NO se publica solo: el workflow lo deja
esperando la aprobación de Andrés (environment «datos-anomalos»). Ver README.

Cada función recibe (limpio_nuevo, indicador_nuevo, limpio_previo, indicador_previo)
y devuelve la lista de motivos (vacía = normal). Sin previo no hay contra qué comparar.
Umbrales: decision-fase0-reporte-SOC-13nov.md (P1).
"""
TRM_VARIACION_MAX = 0.05          # ±5 % frente al último valor publicado
TPM_PASO = 0.25                   # la Junta mueve la tasa en múltiplos de 0,25 puntos
TPM_CAMBIO_MAX = 1.0              # más de 1 punto de una vez es anómalo
IPC_CAMBIO_MAX = 1.5              # puntos de inflación anual frente al último mes publicado
TRM_CONTRASTE_MAX = 0.001         # 0,1 % entre la TRM de la SFC y la del Banco de la República
TOLERANCIA = 0.005                # medio centavo / media centésima: redondeo de la fuente


def _historia(previo, nuevo, nombre):
    """Los valores de periodos ya publicados no pueden cambiar."""
    motivos = []
    for clave, valor in previo.items():
        if clave in nuevo and abs(nuevo[clave] - valor) > TOLERANCIA:
            motivos.append(f"{nombre}: el valor ya publicado de {clave} cambió de {valor} a {nuevo[clave]}")
    return motivos


def trm(limpio, indicador, limpio_previo, indicador_previo):
    motivos = []
    if limpio_previo:
        motivos += _historia({s["vigencia_desde"]: s["valor"] for s in limpio_previo["serie"]},
                             {s["vigencia_desde"]: s["valor"] for s in limpio["serie"]}, "trm")
    if indicador_previo and indicador_previo.get("valor"):
        antes, ahora = indicador_previo["valor"], indicador["valor"]
        if abs(ahora / antes - 1) > TRM_VARIACION_MAX + 1e-9:
            motivos.append(f"trm: pasa de {antes} ({indicador_previo.get('vigencia_desde')}) a {ahora} "
                           f"({indicador['vigencia_desde']}), {100 * (ahora / antes - 1):+.2f} %; el límite es ±5 %")
    return motivos


def tasa_emisor(limpio, indicador, limpio_previo, indicador_previo):
    motivos = []
    if limpio_previo:
        nuevos = {c["desde"]: c["valor"] for c in limpio["cambios"]}
        for c in limpio_previo["cambios"]:
            if c["desde"] not in nuevos:
                motivos.append(f"tasa_emisor: desapareció de la historia el cambio del {c['desde']} ({c['valor']} %)")
        motivos += _historia({c["desde"]: c["valor"] for c in limpio_previo["cambios"]}, nuevos, "tasa_emisor")
    if indicador_previo and indicador_previo.get("valor") is not None:
        cambio = round(indicador["valor"] - indicador_previo["valor"], 6)
        pasos = cambio / TPM_PASO
        if abs(pasos - round(pasos)) > 1e-6:
            motivos.append(f"tasa_emisor: cambia {cambio:+} puntos ({indicador_previo['valor']} → {indicador['valor']}), "
                           "que no es múltiplo de 0,25")
        if abs(cambio) > TPM_CAMBIO_MAX + 1e-9:
            motivos.append(f"tasa_emisor: cambia {cambio:+} puntos de una vez; el límite es 1 punto")
    return motivos


def ipc(limpio, indicador, limpio_previo, indicador_previo):
    motivos = []
    if limpio_previo:
        motivos += _historia(limpio_previo["indices"], limpio["indices"], "ipc")
    if indicador_previo and indicador_previo.get("variacion_anual") is not None:
        antes, ahora = indicador_previo["variacion_anual"], indicador["variacion_anual"]
        if abs(ahora - antes) > IPC_CAMBIO_MAX + 1e-9:
            motivos.append(f"ipc: la inflación anual pasa de {antes} % ({indicador_previo['mes']}) a {ahora} % "
                           f"({indicador['mes']}); el límite es 1,5 puntos")
    return motivos


def cartera_sfc(limpio, indicador, limpio_previo, indicador_previo):
    # La regla de ±10 % frente al corte anterior entra con la Fase 1, cuando la cartera se publique.
    return []


def contraste_trm(serie_sfc, serie_banco):
    """Segunda fuente para la TRM: compara las fechas comunes. Devuelve (motivos, fecha comparada o None).

    serie_sfc y serie_banco: {fecha ISO: valor}. Si no hay fechas comunes, no hay contraste.
    """
    comunes = sorted(set(serie_sfc) & set(serie_banco))
    if not comunes:
        return [], None
    fecha = comunes[-1]
    a, b = serie_sfc[fecha], serie_banco[fecha]
    if abs(a / b - 1) > TRM_CONTRASTE_MAX + 1e-9:
        return [f"trm: el {fecha} la SFC dice {a} y el Banco de la República {b} "
                f"({100 * (a / b - 1):+.3f} %); el límite es 0,1 %"], fecha
    return [], fecha


REVISIONES = {"trm": trm, "tasa_emisor": tasa_emisor, "ipc": ipc, "cartera_sfc": cartera_sfc}
