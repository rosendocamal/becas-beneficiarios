import csv
import sqlite3
from pathlib import Path

from becas import base_datos
from becas.config import CAMPOS, TABLA
from becas.limpieza import ruta_unificada

FILAS = [
    [
        2022,
        "S072",
        4,
        "01",
        "Aguascalientes",
        "005",
        "Jesus Maria",
        "0041",
        "Jesus Gomez",
        5700,
        "2022-02-01",
    ],
    [
        2022,
        "S311",
        4,
        "02",
        "Baja California",
        "003",
        "Tijuana",
        "0123",
        "Otra Localidad",
        1500,
        "",
    ],
]


def crear_csv(tmp_path: Path, anio: int = 2022) -> Path:
    ruta = ruta_unificada(anio, tmp_path / "csv")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(CAMPOS)
        for fila in FILAS:
            escritor.writerow([anio, *fila[1:]])
    return ruta


def test_construir_base_global_y_anual(tmp_path: Path) -> None:
    crear_csv(tmp_path)
    global_db = tmp_path / "db" / "global.db"
    por_anio = tmp_path / "db" / "por_anio"
    conteos = base_datos.construir(
        anios=[2022],
        raiz_csv=tmp_path / "csv",
        ruta_global=global_db,
        raiz_por_anio=por_anio,
        concurrencia=2,
    )
    assert conteos == {2022: 2}
    with sqlite3.connect(global_db) as conexion:
        assert base_datos.contar_registros(conexion) == 2
        assert base_datos.contar_registros(conexion, 2022) == 2
        tablas = [
            fila[0]
            for fila in conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
        assert TABLA in tablas
    with sqlite3.connect(por_anio / "becas_2022.db") as conexion:
        assert base_datos.contar_registros(conexion) == 2


def test_construir_varios_anios(tmp_path: Path) -> None:
    crear_csv(tmp_path, 2022)
    crear_csv(tmp_path, 2023)
    global_db = tmp_path / "db" / "global.db"
    por_anio = tmp_path / "db" / "por_anio"
    conteos = base_datos.construir(
        anios=[2022, 2023],
        raiz_csv=tmp_path / "csv",
        ruta_global=global_db,
        raiz_por_anio=por_anio,
        concurrencia=2,
    )
    assert conteos == {2022: 2, 2023: 2}
    with sqlite3.connect(global_db) as conexion:
        assert base_datos.contar_registros(conexion) == 4
        assert base_datos.contar_registros(conexion, 2023) == 2
    with sqlite3.connect(por_anio / "becas_2023.db") as conexion:
        assert base_datos.contar_registros(conexion) == 2


def test_construir_es_idempotente(tmp_path: Path) -> None:
    crear_csv(tmp_path)
    global_db = tmp_path / "db" / "global.db"
    por_anio = tmp_path / "db" / "por_anio"
    argumentos = {
        "anios": [2022],
        "raiz_csv": tmp_path / "csv",
        "ruta_global": global_db,
        "raiz_por_anio": por_anio,
        "concurrencia": 2,
    }
    base_datos.construir(**argumentos)
    base_datos.construir(**argumentos)
    with sqlite3.connect(global_db) as conexion:
        assert base_datos.contar_registros(conexion) == 2
