import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import MANIFIESTO, ORGANIZACION, PATRON_DATASET, RUTA_API, URL_PRINCIPAL
from .modelos import Recurso
from .parseo import extraer_estado, extraer_trimestre

CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}


def crear_sesion() -> requests.Session:
    sesion = requests.Session()
    sesion.headers.update(CABECERAS)
    reintentos = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset({"GET"}),
    )
    adaptador = HTTPAdapter(max_retries=reintentos)
    sesion.mount("https://", adaptador)
    sesion.mount("http://", adaptador)
    return sesion


def url_api(url_principal: str) -> str:
    return urljoin(url_principal.rstrip("/") + "/", RUTA_API)


def comprobar_respuesta(respuesta: requests.Response, url: str) -> None:
    try:
        respuesta.raise_for_status()
    except requests.HTTPError as error:
        if respuesta.status_code == 403:
            raise RuntimeError(
                f"Acceso rechazado (403) en {url}. "
                "Consulta la sección de solución de problemas del README.md."
            ) from error
        raise


def consultar_api(
    sesion: requests.Session, url: str, parametros: dict[str, str | int]
) -> dict[str, object]:
    respuesta = sesion.get(url, params=parametros, timeout=60)
    comprobar_respuesta(respuesta, url)
    contenido = respuesta.json()
    if not contenido.get("success"):
        raise RuntimeError(f"La API devolvió un error: {contenido.get('error', {})}")
    return dict(contenido["result"])


def _lista_diccionarios(valor: object) -> list[dict[str, object]]:
    if not isinstance(valor, list):
        return []
    return [dict(entry) for entry in valor if isinstance(entry, dict)]


def _texto(valor: object) -> str | None:
    return str(valor) if valor else None


def procesar_paquete(paquete: dict[str, object]) -> list[Recurso]:
    slug = str(paquete.get("name", ""))
    coincidencia = PATRON_DATASET.match(slug)
    if coincidencia is None:
        return []
    anio = int(coincidencia.group(1))
    programa = coincidencia.group(2).upper()
    recursos: list[Recurso] = []
    for datos in _lista_diccionarios(paquete.get("resources")):
        url = str(datos.get("url", ""))
        if not url.lower().split("?")[0].endswith(".csv"):
            continue
        nombre = str(datos.get("name") or "")
        estado = extraer_estado(url)
        trimestre = extraer_trimestre(url) or extraer_trimestre(nombre)
        if estado is None or trimestre is None:
            raise ValueError(f"No se pudo interpretar el recurso: {url}")
        cve_edo, nom_edo = estado
        recursos.append(
            Recurso(
                anio=anio,
                programa=programa,
                cve_edo=cve_edo,
                nom_edo=nom_edo,
                trimestre=trimestre,
                url=url,
                id_recurso=str(datos.get("id") or ""),
                nombre=nombre,
                actualizado=_texto(datos.get("last_modified") or paquete.get("metadata_modified")),
            )
        )
    return recursos


def descubrir(
    url_principal: str = URL_PRINCIPAL,
    organizacion: str = ORGANIZACION,
    sesion: requests.Session | None = None,
) -> list[Recurso]:
    sesion = sesion or crear_sesion()
    url = urljoin(url_api(url_principal), "package_search")
    encontrados: dict[tuple[int, str, str, int], Recurso] = {}
    iniciar = 0
    while True:
        resultado = consultar_api(
            sesion,
            url,
            {"fq": f"organization:{organizacion}", "rows": 1000, "start": iniciar},
        )
        paquetes = _lista_diccionarios(resultado.get("results"))
        for paquete in paquetes:
            for recurso in procesar_paquete(paquete):
                clave = (recurso.anio, recurso.programa, recurso.cve_edo, recurso.trimestre)
                encontrados.setdefault(clave, recurso)
        iniciar += len(paquetes)
        total = int(str(resultado.get("count", 0)))
        if not paquetes or iniciar >= total:
            break
    return sorted(
        encontrados.values(),
        key=lambda recurso: (
            recurso.anio,
            recurso.programa,
            recurso.cve_edo,
            recurso.trimestre,
        ),
    )


def guardar_manifiesto(recursos: list[Recurso], ruta: Path = MANIFIESTO) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".json.tmp")
    temporal.write_text(
        json.dumps([recurso.to_dict() for recurso in recursos], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporal.replace(ruta)
    return ruta


def cargar_manifiesto(ruta: Path = MANIFIESTO) -> list[Recurso]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return [Recurso.from_dict(entry) for entry in _lista_diccionarios(datos)]
