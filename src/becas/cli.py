import argparse
from pathlib import Path

from . import base_datos, descarga, descubrimiento, limpieza
from .config import MANIFIESTO, ORGANIZACION, URL_PRINCIPAL
from .descarga import FUENTES


def comando_descubrir(args: argparse.Namespace) -> None:
    recursos = descubrimiento.descubrir(args.url_principal, args.organizacion)
    ruta = descubrimiento.guardar_manifiesto(recursos, args.manifiesto)
    anios = sorted({recurso.anio for recurso in recursos})
    print(f"{len(recursos)} recursos en {ruta}")
    print(f"Años: {', '.join(str(anio) for anio in anios)}")


def comando_descargar(args: argparse.Namespace) -> None:
    recursos = descubrimiento.cargar_manifiesto(args.manifiesto)
    descarga.descargar(
        recursos,
        fuerza=args.fuerza,
        concurrencia=args.concurrencia_descarga,
        fuente=args.fuente_csv,
    )


def comando_limpiar(args: argparse.Namespace) -> None:
    recursos = descubrimiento.cargar_manifiesto(args.manifiesto)
    anios = sorted({recurso.anio for recurso in recursos})
    for anio in anios:
        print(f"Unificando {anio}")
        limpieza.unificar_anio(anio, recursos, concurrencia=args.concurrencia_limpieza)


def comando_cargar(args: argparse.Namespace) -> None:
    base_datos.construir(
        args.anio,
        concurrencia=args.concurrencia_limpieza,
        lote=args.lote,
        cache_mib=args.cache_mib,
    )


def comando_todo(args: argparse.Namespace) -> None:
    comando_descubrir(args)
    comando_descargar(args)
    comando_limpiar(args)
    args.anio = None
    comando_cargar(args)


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="becas", description="Consolida los padrones de becas de datos.gob.mx"
    )
    parser.add_argument("--url-principal", default=URL_PRINCIPAL)
    parser.add_argument("--organizacion", default=ORGANIZACION)
    parser.add_argument("--manifiesto", type=Path, default=MANIFIESTO)
    parser.add_argument("--fuente-csv", choices=FUENTES, default="datastore")
    parser.add_argument("--concurrencia-descarga", type=int)
    parser.add_argument("--concurrencia-limpieza", type=int)
    parser.add_argument("--lote", type=int)
    parser.add_argument("--cache-mib", type=int)
    parser.add_argument("--secuencial", action="store_true")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    descubrir = subcomandos.add_parser("descubrir", help="Genera el manifiesto de recursos CSV")
    descubrir.set_defaults(func=comando_descubrir)

    descargar = subcomandos.add_parser("descargar", help="Descarga los CSV a data/raw")
    descargar.add_argument("--fuerza", action="store_true")
    descargar.set_defaults(func=comando_descargar)

    limpiar = subcomandos.add_parser("limpiar", help="Limpia y unifica los CSV por año")
    limpiar.set_defaults(func=comando_limpiar)

    cargar = subcomandos.add_parser("cargar", help="Construye la base global y las bases por año")
    cargar.add_argument("--anio", type=int, nargs="*")
    cargar.set_defaults(func=comando_cargar)

    todo = subcomandos.add_parser("todo", help="Ejecuta todas las etapas")
    todo.add_argument("--fuerza", action="store_true")
    todo.set_defaults(func=comando_todo)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = crear_parser().parse_args(argv)
    if args.secuencial:
        args.concurrencia_descarga = 1
        args.concurrencia_limpieza = 1
    args.func(args)
    return 0
