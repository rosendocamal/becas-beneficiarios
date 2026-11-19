import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import CAMPOS, CSV_ANUALES, INTERMEDIOS, RAW
from .descarga import ruta_raw
from .modelos import Recurso
from .parseo import (
    detectar_delimitador,
    extraer_trimestre,
    normalizar_beca,
    normalizar_encabezado,
    normalizar_fecha,
    normalizar_texto,
)
from .rendimiento import capacidad as detectar_capacidad


def ruta_intermedia(recurso: Recurso, raiz: Path = INTERMEDIOS) -> Path:
    return raiz / str(recurso.anio) / recurso.programa / recurso.nombre_archivo


def ruta_unificada(anio: int, raiz: Path = CSV_ANUALES) -> Path:
    return raiz / f"becas_{anio}.csv"


def valor_fila(fila: dict[str, str | None], campos: dict[str, str], nombre: str) -> str | None:
    clave = campos.get(nombre)
    return fila.get(clave) if clave is not None else None


def construir_registro(
    recurso: Recurso, fila: dict[str, str | None], campos: dict[str, str]
) -> dict[str, object]:
    cve_edo = normalizar_texto(valor_fila(fila, campos, "cve_edo")) or recurso.cve_edo
    if cve_edo.isdigit():
        cve_edo = cve_edo.zfill(2)
    nom_edo = normalizar_texto(valor_fila(fila, campos, "nom_edo")) or recurso.nom_edo
    trimestre_texto = normalizar_texto(valor_fila(fila, campos, "trimestre"))
    trimestre = extraer_trimestre(trimestre_texto or "") or recurso.trimestre
    return {
        "anio": recurso.anio,
        "programa": recurso.programa,
        "trimestre": trimestre,
        "cve_edo": cve_edo,
        "nom_edo": nom_edo,
        "cve_mun": normalizar_texto(valor_fila(fila, campos, "cve_mun")),
        "nom_mun": normalizar_texto(valor_fila(fila, campos, "nom_mun")),
        "cve_loc": normalizar_texto(valor_fila(fila, campos, "cve_loc")),
        "nom_loc": normalizar_texto(valor_fila(fila, campos, "nom_loc")),
        "beca": normalizar_beca(valor_fila(fila, campos, "beca")),
        "fecha_alta": normalizar_fecha(valor_fila(fila, campos, "fecha_alta")),
    }


def limpiar_recurso(recurso: Recurso, origen: Path, destino: Path) -> int:
    with origen.open("r", encoding="utf-8-sig", errors="replace", newline="") as entrada:
        primera_linea = entrada.readline()
        delimitador = detectar_delimitador(primera_linea)
        entrada.seek(0)
        lector = csv.DictReader(entrada, delimiter=delimitador)
        if lector.fieldnames is None:
            raise ValueError(f"El archivo no tiene encabezado: {origen}")
        campos = {normalizar_encabezado(nombre): nombre for nombre in lector.fieldnames}
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("w", encoding="utf-8", newline="") as salida:
            escritor = csv.DictWriter(salida, fieldnames=CAMPOS, extrasaction="ignore")
            escritor.writeheader()
            total = 0
            for fila in lector:
                escritor.writerow(construir_registro(recurso, fila, campos))
                total += 1
    return total


def _limpiar_indice(
    indice: int, recurso: Recurso, raiz_raw: Path, raiz_intermedia: Path
) -> tuple[int, int]:
    origen = ruta_raw(recurso, raiz_raw)
    intermedio = ruta_intermedia(recurso, raiz_intermedia)
    total = limpiar_recurso(recurso, origen, intermedio)
    return indice, total


def _volcar_intermedio(escritor: Any, intermedio: Path) -> None:
    with intermedio.open("r", encoding="utf-8", newline="") as entrada:
        lector = csv.reader(entrada)
        next(lector, None)
        for fila in lector:
            escritor.writerow(fila)


def unificar_anio(
    anio: int,
    recursos: list[Recurso],
    raiz_raw: Path = RAW,
    raiz_intermedia: Path = INTERMEDIOS,
    raiz_csv: Path = CSV_ANUALES,
    concurrencia: int | None = None,
) -> Path:
    seleccionados = sorted(
        (recurso for recurso in recursos if recurso.anio == anio),
        key=lambda recurso: (recurso.programa, recurso.cve_edo, recurso.trimestre),
    )
    if not seleccionados:
        raise ValueError(f"No hay recursos para el año {anio}")
    config = detectar_capacidad(concurrencia_limpieza=concurrencia)
    destino = ruta_unificada(anio, raiz_csv)
    destino.parent.mkdir(parents=True, exist_ok=True)
    conteos: dict[int, int] = {}
    if config.limpiezas == 1:
        for indice, recurso in enumerate(seleccionados):
            total = limpiar_recurso(
                recurso, ruta_raw(recurso, raiz_raw), ruta_intermedia(recurso, raiz_intermedia)
            )
            conteos[indice] = total
    else:
        with ProcessPoolExecutor(max_workers=config.limpiezas) as executor:
            futuros = [
                executor.submit(_limpiar_indice, indice, recurso, raiz_raw, raiz_intermedia)
                for indice, recurso in enumerate(seleccionados)
            ]
            for futuro in as_completed(futuros):
                indice, total = futuro.result()
                conteos[indice] = total
    with destino.open("w", encoding="utf-8", newline="") as unificado:
        escritor = csv.writer(unificado)
        escritor.writerow(CAMPOS)
        for indice, recurso in enumerate(seleccionados):
            intermedio = ruta_intermedia(recurso, raiz_intermedia)
            print(f"[{indice + 1:04d}/{len(seleccionados)}] {intermedio.name}")
            _volcar_intermedio(escritor, intermedio)
            print(f"  {conteos[indice]} registros")
    return destino
