import pytest

import becas.rendimiento as rendimiento


def test_capacidad_con_equipo_medido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendimiento.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(rendimiento, "memoria_disponible_mib", lambda: 18432)
    config = rendimiento.capacidad()
    assert config.cpus == 12
    assert config.descargas == 8
    assert config.limpiezas == 10
    assert config.lote == 20000
    assert config.cache_kib == 512 * 1024
    assert config.fragmento == 1 << 20


def test_capacidad_con_poca_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendimiento.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(rendimiento, "memoria_disponible_mib", lambda: 1024)
    config = rendimiento.capacidad()
    assert config.limpiezas == 1
    assert config.cache_kib == 128 * 1024


def test_capacidad_respeta_opciones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rendimiento.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(rendimiento, "memoria_disponible_mib", lambda: 18432)
    config = rendimiento.capacidad(
        concurrencia_descarga=3, concurrencia_limpieza=2, lote=100, cache_mib=64
    )
    assert config.descargas == 3
    assert config.limpiezas == 2
    assert config.lote == 100
    assert config.cache_kib == 64 * 1024
