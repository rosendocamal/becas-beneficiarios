import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Capacidad:
    cpus: int
    memoria_disponible_mib: int
    descargas: int
    limpiezas: int
    lote: int
    cache_kib: int
    fragmento: int


def memoria_disponible_mib() -> int:
    try:
        for linea in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if linea.startswith("MemAvailable:"):
                return int(linea.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        paginas = int(os.sysconf("SC_AVPHYS_PAGES"))
        tamano = int(os.sysconf("SC_PAGE_SIZE"))
        return paginas * tamano // (1024 * 1024)
    except (OSError, ValueError):
        return 2048


def capacidad(
    concurrencia_descarga: int | None = None,
    concurrencia_limpieza: int | None = None,
    lote: int | None = None,
    cache_mib: int | None = None,
) -> Capacidad:
    cpus = os.cpu_count() or 2
    disponible = memoria_disponible_mib()
    reserva = max(2048, disponible * 15 // 100)
    utilizable = max(512, disponible - reserva)
    descargas = concurrencia_descarga or min(8, max(1, cpus - 2))
    limpiezas = concurrencia_limpieza or max(1, min(cpus - 2, utilizable // 512))
    tamano_lote = lote or 20000
    cache = cache_mib or max(128, min(512, utilizable // 8))
    return Capacidad(
        cpus=cpus,
        memoria_disponible_mib=disponible,
        descargas=max(1, descargas),
        limpiezas=max(1, limpiezas),
        lote=max(1, tamano_lote),
        cache_kib=cache * 1024,
        fragmento=1 << 20,
    )
