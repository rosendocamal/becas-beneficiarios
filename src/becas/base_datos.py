import csv
import sqlite3
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from pathlib import Path

from .config import BASE_GLOBAL, BASE_POR_ANIO, CAMPOS, CSV_ANUALES, INDICES, TABLA, TIPOS
from .limpieza import ruta_unificada
from .rendimiento import capacidad as detectar_capacidad


def configurar_conexion(conexion: sqlite3.Connection, cache_kib: int) -> None:
    conexion.execute(f"PRAGMA cache_size = {cache_kib}")
    conexion.execute("PRAGMA temp_store = MEMORY")
    conexion.execute("PRAGMA synchronous = OFF")
    conexion.execute("PRAGMA journal_mode = MEMORY")


def crear_esquema(conexion: sqlite3.Connection, con_indices: bool = True) -> None:
    columnas = ", ".join(f"{nombre} {tipo}" for nombre, tipo in TIPOS.items())
    conexion.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLA} (id INTEGER PRIMARY KEY AUTOINCREMENT, {columnas})"
    )
    if con_indices:
        crear_indices(conexion)
    conexion.commit()


def crear_indices(conexion: sqlite3.Connection) -> None:
    for indice in INDICES:
        conexion.execute(indice)
    conexion.commit()


def vaciar_anio(conexion: sqlite3.Connection, anio: int, con_indices: bool = True) -> None:
    crear_esquema(conexion, con_indices)
    conexion.execute(f"DELETE FROM {TABLA} WHERE anio = ?", (anio,))
    conexion.commit()


def convertir_fila(fila: list[str]) -> tuple[object, ...]:
    valores: list[object] = []
    for nombre, texto in zip(CAMPOS, fila, strict=True):
        if texto == "":
            valores.append(None)
        elif nombre in {"anio", "trimestre"}:
            valores.append(int(texto))
        elif nombre == "beca":
            valores.append(float(texto))
        else:
            valores.append(texto)
    return tuple(valores)


def contar_registros(conexion: sqlite3.Connection, anio: int | None = None) -> int:
    if anio is None:
        fila = conexion.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()
    else:
        fila = conexion.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE anio = ?", (anio,)).fetchone()
    return int(fila[0])


def cargar_csv(conexion: sqlite3.Connection, ruta: Path, anio: int, tamano_lote: int = 5000) -> int:
    crear_esquema(conexion, con_indices=False)
    consulta = f"INSERT INTO {TABLA} ({','.join(CAMPOS)}) VALUES ({','.join('?' for _ in CAMPOS)})"
    total = 0
    with ruta.open("r", encoding="utf-8", newline="") as archivo:
        lector = csv.reader(archivo)
        cabecera = next(lector, None)
        if tuple(cabecera or ()) != CAMPOS:
            raise ValueError(f"Encabezado inesperado en {ruta}: {cabecera}")
        lote: list[tuple[object, ...]] = []
        for fila in lector:
            if not fila:
                continue
            lote.append(convertir_fila(fila))
            if len(lote) >= tamano_lote:
                conexion.executemany(consulta, lote)
                total += len(lote)
                lote.clear()
        if lote:
            conexion.executemany(consulta, lote)
            total += len(lote)
    conexion.commit()
    return total


def _construir_base_anio(tarea: tuple[int, Path, Path, int, int]) -> tuple[int, int]:
    anio, ruta_csv, ruta_db, tamano_lote, cache_kib = tarea
    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(ruta_db)) as conexion:
        configurar_conexion(conexion, cache_kib)
        vaciar_anio(conexion, anio, con_indices=False)
        total = cargar_csv(conexion, ruta_csv, anio, tamano_lote)
        crear_indices(conexion)
    return anio, total


def _ensamblar_global(
    rutas: list[tuple[int, Path]],
    conteos_anuales: dict[int, int],
    ruta_global: Path,
    cache_kib: int,
) -> int:
    columnas = ",".join(CAMPOS)
    with closing(sqlite3.connect(ruta_global)) as conexion:
        configurar_conexion(conexion, cache_kib)
        crear_esquema(conexion, con_indices=False)
        conexion.execute(f"DELETE FROM {TABLA}")
        conexion.commit()
        total = 0
        for anio, ruta_anual in rutas:
            alias = f"anio_{anio}"
            conexion.execute(f"ATTACH DATABASE ? AS {alias}", (str(ruta_anual),))
            fila = conexion.execute(f"SELECT COUNT(*) FROM {alias}.{TABLA}").fetchone()
            total_anio = int(fila[0])
            if total_anio != conteos_anuales[anio]:
                raise RuntimeError(
                    f"Los conteos no coinciden para {anio}: {total_anio} vs {conteos_anuales[anio]}"
                )
            conexion.execute(
                f"INSERT INTO main.{TABLA} ({columnas}) "
                f"SELECT {columnas} FROM {alias}.{TABLA} ORDER BY id"
            )
            total += total_anio
            conexion.commit()
            conexion.execute(f"DETACH DATABASE {alias}")
        crear_indices(conexion)
        conexion.commit()
        return total


def construir(
    anios: Iterable[int] | None = None,
    raiz_csv: Path = CSV_ANUALES,
    ruta_global: Path = BASE_GLOBAL,
    raiz_por_anio: Path = BASE_POR_ANIO,
    concurrencia: int | None = None,
    lote: int | None = None,
    cache_mib: int | None = None,
) -> dict[int, int]:
    if anios is None:
        rutas = sorted(raiz_csv.glob("becas_*.csv"))
    else:
        rutas = [ruta_unificada(anio, raiz_csv) for anio in anios]
    if not rutas:
        raise FileNotFoundError(f"No hay CSV unificados en {raiz_csv}")
    config = detectar_capacidad(concurrencia_limpieza=concurrencia, lote=lote, cache_mib=cache_mib)
    ruta_global.parent.mkdir(parents=True, exist_ok=True)
    raiz_por_anio.mkdir(parents=True, exist_ok=True)
    pares = [(int(ruta.stem.rsplit("_", 1)[-1]), ruta) for ruta in rutas]
    tareas = [
        (anio, ruta_csv, raiz_por_anio / f"becas_{anio}.db", config.lote, config.cache_kib)
        for anio, ruta_csv in pares
    ]
    with ProcessPoolExecutor(max_workers=config.limpiezas) as executor:
        resultados = dict(executor.map(_construir_base_anio, tareas))
    rutas_db = [(anio, raiz_por_anio / f"becas_{anio}.db") for anio, _ in pares]
    total = _ensamblar_global(rutas_db, resultados, ruta_global, config.cache_kib)
    for anio, total_anio in resultados.items():
        print(f"{anio}: {total_anio} registros cargados")
    print(f"Total global: {total} registros")
    return resultados
