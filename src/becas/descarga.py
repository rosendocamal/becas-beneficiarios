import csv
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from curl_cffi import requests as curl_requests

from .config import RAW, RUTA_API, URL_PRINCIPAL
from .descubrimiento import comprobar_respuesta, crear_sesion
from .modelos import Recurso
from .parseo import detectar_delimitador
from .rendimiento import capacidad as detectar_capacidad

FUENTES = ("datastore", "directo", "auto")
LIMITE_DATASTORE = 32000
DescargadorDirecto = Callable[[Recurso, Path, int], Path]


def ruta_raw(recurso: Recurso, raiz: Path = RAW) -> Path:
    return raiz / str(recurso.anio) / recurso.programa / recurso.nombre_archivo


def validar_csv(ruta: Path) -> None:
    with ruta.open("rb") as archivo:
        primera_linea = archivo.readline().decode("utf-8-sig", errors="replace")
    if not primera_linea.strip() or detectar_delimitador(primera_linea) not in {",", ";"}:
        raise ValueError(f"El archivo no parece un CSV válido: {ruta}")
    if len(primera_linea.split(detectar_delimitador(primera_linea))) < 5:
        raise ValueError(f"El CSV tiene muy pocas columnas: {ruta}")


def descargar_directo(
    recurso: Recurso, destino: Path, sesion: requests.Session, fragmento: int = 1 << 20
) -> Path:
    temporal = destino.with_suffix(".csv.tmp")
    with sesion.get(
        recurso.url,
        stream=True,
        timeout=(15, 120),
        headers={"Accept": "text/csv,*/*"},
    ) as respuesta:
        comprobar_respuesta(respuesta, recurso.url)
        with temporal.open("wb") as archivo:
            for bloque in respuesta.iter_content(chunk_size=fragmento):
                if bloque:
                    archivo.write(bloque)
    validar_csv(temporal)
    temporal.replace(destino)
    return destino


def descargar_directo_navegador(recurso: Recurso, destino: Path, fragmento: int = 1 << 20) -> Path:
    temporal = destino.with_suffix(".csv.tmp")
    respuesta = curl_requests.get(
        recurso.url,
        impersonate="chrome",
        stream=True,
        timeout=(15, 120),
        headers={"Accept": "text/csv,*/*"},
    )
    respuesta_any: Any = respuesta
    try:
        if respuesta.status_code != 200:
            raise RuntimeError(
                f"Descarga directa rechazada ({respuesta.status_code}): {recurso.url}"
            )
        with temporal.open("wb") as archivo:
            for bloque in respuesta_any.iter_content(chunk_size=fragmento):
                if bloque:
                    archivo.write(bloque)
    finally:
        respuesta_any.close()
    validar_csv(temporal)
    temporal.replace(destino)
    return destino


def descargar_datastore(
    recurso: Recurso,
    destino: Path,
    sesion: requests.Session,
    url_principal: str = URL_PRINCIPAL,
    limite: int = LIMITE_DATASTORE,
) -> Path:
    if not recurso.id_recurso:
        raise ValueError(f"El recurso no tiene identificador de datastore: {recurso.url}")
    url = urljoin(url_principal.rstrip("/") + "/", f"{RUTA_API}datastore_search")
    parametros: dict[str, str | int] = {
        "resource_id": recurso.id_recurso,
        "limit": 1,
    }
    respuesta = sesion.get(url, params=parametros, timeout=(15, 120))
    comprobar_respuesta(respuesta, url)
    contenido = respuesta.json()
    if not contenido.get("success"):
        raise RuntimeError(f"Falló la consulta al datastore: {recurso.id_recurso}")
    resultado = contenido["result"]
    total = int(resultado["total"])
    campos = [str(campo["id"]) for campo in resultado["fields"] if campo["id"] != "_id"]
    if not campos:
        raise ValueError(f"El datastore no devolvió columnas: {recurso.id_recurso}")
    temporal = destino.with_suffix(".csv.tmp")
    desplazamiento = 0
    with temporal.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(campos)
        archivo.flush()
        while desplazamiento < total:
            parametros = {
                "resource_id": recurso.id_recurso,
                "limit": limite,
                "offset": desplazamiento,
                "records_format": "csv",
                "fields": ",".join(campos),
            }
            respuesta = sesion.get(url, params=parametros, timeout=(15, 120))
            comprobar_respuesta(respuesta, url)
            contenido = respuesta.json()
            if not contenido.get("success"):
                raise RuntimeError(f"Falló la consulta al datastore: {recurso.id_recurso}")
            registros = contenido["result"]["records"]
            if isinstance(registros, str):
                if not registros:
                    break
                archivo.write(registros)
                if not registros.endswith("\n"):
                    archivo.write("\n")
                desplazamiento += len(registros.splitlines())
            else:
                escritor_registros = csv.DictWriter(
                    archivo, fieldnames=campos, extrasaction="ignore"
                )
                for registro in registros:
                    escritor_registros.writerow(registro)
                desplazamiento += len(registros)
                if not registros:
                    break
    validar_csv(temporal)
    temporal.replace(destino)
    return destino


def descargar_recurso(
    recurso: Recurso,
    destino: Path,
    sesion: requests.Session | None = None,
    url_principal: str = URL_PRINCIPAL,
    fuerza: bool = False,
    fragmento: int = 1 << 20,
    fuente: str = "datastore",
    descargar_directa: DescargadorDirecto | None = None,
) -> Path:
    if fuente not in FUENTES:
        raise ValueError(f"Fuente desconocida: {fuente}. Usa {', '.join(FUENTES)}")
    sesion = sesion or crear_sesion()
    directa = descargar_directa or descargar_directo_navegador
    if destino.exists() and destino.stat().st_size > 0 and not fuerza:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    if fuente == "datastore":
        try:
            return descargar_datastore(recurso, destino, sesion, url_principal)
        except (requests.RequestException, RuntimeError, ValueError):
            return directa(recurso, destino, fragmento)
    if fuente == "directo":
        return directa(recurso, destino, fragmento)
    try:
        return directa(recurso, destino, fragmento)
    except (requests.RequestException, RuntimeError, ValueError):
        return descargar_datastore(recurso, destino, sesion, url_principal)


def _descargar_indice(
    indice: int,
    recurso: Recurso,
    raiz: Path,
    fabricar_sesion: Callable[[], requests.Session],
    url_principal: str,
    fuerza: bool,
    fragmento: int,
    fuente: str,
    descargar_directa: DescargadorDirecto,
) -> tuple[int, Path]:
    destino = ruta_raw(recurso, raiz)
    ruta = descargar_recurso(
        recurso,
        destino,
        fabricar_sesion(),
        url_principal,
        fuerza,
        fragmento,
        fuente,
        descargar_directa,
    )
    print(f"[{indice + 1:04d}] {recurso.anio} {recurso.programa} {destino.name}")
    return indice, ruta


def descargar(
    recursos: list[Recurso],
    raiz: Path = RAW,
    url_principal: str = URL_PRINCIPAL,
    fuerza: bool = False,
    concurrencia: int | None = None,
    fragmento: int | None = None,
    fabricar_sesion: Callable[[], requests.Session] | None = None,
    fuente: str = "datastore",
    descargar_directa: DescargadorDirecto | None = None,
) -> list[Path]:
    config = detectar_capacidad(concurrencia_descarga=concurrencia)
    fabricar = fabricar_sesion or crear_sesion
    directa = descargar_directa or descargar_directo_navegador
    tamanio = fragmento or config.fragmento
    resultados: dict[int, Path] = {}
    if config.descargas == 1:
        for indice, recurso in enumerate(recursos):
            posicion, ruta = _descargar_indice(
                indice, recurso, raiz, fabricar, url_principal, fuerza, tamanio, fuente, directa
            )
            resultados[posicion] = ruta
    else:
        with ThreadPoolExecutor(max_workers=config.descargas) as executor:
            futuros = [
                executor.submit(
                    _descargar_indice,
                    indice,
                    recurso,
                    raiz,
                    fabricar,
                    url_principal,
                    fuerza,
                    tamanio,
                    fuente,
                    directa,
                )
                for indice, recurso in enumerate(recursos)
            ]
            for futuro in as_completed(futuros):
                posicion, ruta = futuro.result()
                resultados[posicion] = ruta
    return [resultados[indice] for indice in range(len(recursos))]
