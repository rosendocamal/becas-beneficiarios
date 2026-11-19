import pytest

from becas.parseo import (
    detectar_delimitador,
    extraer_estado,
    extraer_trimestre,
    normalizar_beca,
    normalizar_encabezado,
    normalizar_fecha,
    normalizar_texto,
)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("S072_EDO_01_Aguascalientes_4to_Trim2022.csv", 4),
        ("s072_edo_03_baja_california_sur_2do_trimestre.csv", 2),
        ("Beneficiarios en Jalisco (3er. trim. 2026)", 3),
        ("s311_edo_01_aguascalientes_1er_trimestre.csv", 1),
        ("archivo_sin_trimestre.csv", None),
    ],
)
def test_extraer_trimestre(texto: str, esperado: int | None) -> None:
    assert extraer_trimestre(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("S072_EDO_01_Aguascalientes_4to_Trim2022.csv", ("01", "Aguascalientes")),
        ("s072_edo_03_baja_caifornia_sur_2do_trimestre.csv", ("03", "Baja California Sur")),
        ("S311_EDO_09_Ciudad_de_Mexico_4to_Trim2025.csv", ("09", "Ciudad de México")),
        ("sin_estado.csv", None),
    ],
)
def test_extraer_estado(texto: str, esperado: tuple[str, str] | None) -> None:
    assert extraer_estado(texto) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("2019-01-01", "2019-01-01"),
        ("01/02/2020", "2020-02-01"),
        ("31-12-2025", "2025-12-31"),
        ("01-01-0001", None),
        ("", None),
    ],
)
def test_normalizar_fecha(valor: str, esperado: str | None) -> None:
    assert normalizar_fecha(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("5700", 5700.0), ("1,234.50", 1234.5), ('"2500"', 2500.0), ("", None), ("abc", None)],
)
def test_normalizar_beca(valor: str, esperado: float | None) -> None:
    assert normalizar_beca(valor) == esperado


def test_normalizar_encabezado() -> None:
    assert normalizar_encabezado("CVE_EDO") == "cve_edo"
    assert normalizar_encabezado("Fecha Alta") == "fecha_alta"
    assert normalizar_encabezado("NOM-MUN") == "nom_mun"


def test_normalizar_texto() -> None:
    assert normalizar_texto("  Jesus  Maria ") == "Jesus Maria"
    assert normalizar_texto("   ") is None


def test_detectar_delimitador() -> None:
    assert detectar_delimitador("a;b;c") == ";"
    assert detectar_delimitador("a,b,c") == ","
