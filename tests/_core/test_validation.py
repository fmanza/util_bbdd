"""Tests para validadores centralizados (_core/validation/)."""

from __future__ import annotations

import numpy as np
import pytest

from util_bbdd._core.validation import validate_batch_config, validate_chunk_size, validate_commit_cadence


class TestValidateChunkSize:
    """Tests para validate_chunk_size()."""

    def test_valid_chunk_size_int(self) -> None:
        """Enteros ≥ 1 son válidos."""
        assert validate_chunk_size(1) == 1
        assert validate_chunk_size(5000) == 5000
        assert validate_chunk_size(100_000) == 100_000

    def test_valid_chunk_size_numpy_int(self) -> None:
        """Enteros de numpy son válidos (``operator.index`` es soportado)."""
        assert validate_chunk_size(np.int64(5000)) == 5000
        assert validate_chunk_size(np.int32(100)) == 100

    def test_invalid_chunk_size_zero(self) -> None:
        """chunk_size=0 debe raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(0)

    def test_invalid_chunk_size_negative(self) -> None:
        """chunk_size negativo debe raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(-1)
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(-1000)

    def test_invalid_chunk_size_bool(self) -> None:
        """chunk_size como bool debe raise ValueError (bool es un int en Python, pero lo rechazamos)."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(True)
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(False)

    def test_invalid_chunk_size_float(self) -> None:
        """chunk_size como float debe raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(5000.5)

    def test_invalid_chunk_size_string(self) -> None:
        """chunk_size como string debe raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size("5000")

    def test_invalid_chunk_size_none(self) -> None:
        """chunk_size como None debe raise ValueError."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_chunk_size(None)


class TestValidateCommitCadence:
    """Tests para validate_commit_cadence()."""

    def test_valid_commit_cadence_none(self) -> None:
        """commit_every_n_chunks=None es válido (sin commits periódicos)."""
        assert validate_commit_cadence(None) is None

    def test_valid_commit_cadence_int(self) -> None:
        """commit_every_n_chunks como entero ≥ 1 es válido."""
        assert validate_commit_cadence(1) == 1
        assert validate_commit_cadence(5000) == 5000
        assert validate_commit_cadence(100_000) == 100_000

    def test_valid_commit_cadence_numpy_int(self) -> None:
        """commit_every_n_chunks como numpy int es válido (``operator.index`` soportado)."""
        assert validate_commit_cadence(np.int64(5000)) == 5000
        assert validate_commit_cadence(np.int32(100)) == 100

    def test_invalid_commit_cadence_zero(self) -> None:
        """commit_every_n_chunks=0 debe raise ValueError."""
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_commit_cadence(0)

    def test_invalid_commit_cadence_negative(self) -> None:
        """commit_every_n_chunks negativo debe raise ValueError."""
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_commit_cadence(-1)

    def test_invalid_commit_cadence_bool(self) -> None:
        """commit_every_n_chunks como bool debe raise ValueError."""
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_commit_cadence(True)
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_commit_cadence(False)

    def test_invalid_commit_cadence_float(self) -> None:
        """commit_every_n_chunks como float debe raise ValueError."""
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_commit_cadence(5000.5)

    def test_invalid_commit_cadence_string(self) -> None:
        """commit_every_n_chunks como string debe raise ValueError."""
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_commit_cadence("5000")


class TestValidateBatchConfig:
    """Tests para validate_batch_config()."""

    def test_valid_batch_config_defaults(self) -> None:
        """Configuración válida con defaults."""
        chunk_size, commit_cadence, write_batch = validate_batch_config(5000)
        assert chunk_size == 5000
        assert commit_cadence is None
        assert write_batch is None

    def test_valid_batch_config_full(self) -> None:
        """Configuración válida con todos los parámetros."""
        chunk_size, commit_cadence, write_batch = validate_batch_config(
            chunk_size=5000, commit_every_n_chunks=10000, write_batch_size=20000
        )
        assert chunk_size == 5000
        assert commit_cadence == 10000
        assert write_batch == 20000

    def test_valid_batch_config_numpy_ints(self) -> None:
        """Configuración válida con numpy ints (``operator.index`` soportado)."""
        chunk_size, commit_cadence, write_batch = validate_batch_config(
            chunk_size=np.int64(5000), commit_every_n_chunks=np.int32(10000), write_batch_size=np.int64(20000)
        )
        assert chunk_size == 5000
        assert commit_cadence == 10000
        assert write_batch == 20000

    def test_invalid_chunk_size_raises(self) -> None:
        """Si chunk_size es inválido, validate_batch_config() debe raise."""
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            validate_batch_config(chunk_size=0)

    def test_invalid_commit_cadence_raises(self) -> None:
        """Si commit_every_n_chunks es inválido, validate_batch_config() debe raise."""
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            validate_batch_config(chunk_size=5000, commit_every_n_chunks=-1)

    def test_invalid_write_batch_raises(self) -> None:
        """Si write_batch_size es inválido, validate_batch_config() debe raise."""
        with pytest.raises(ValueError, match="write_batch_size debe ser None o un entero ≥ 1"):
            validate_batch_config(chunk_size=5000, write_batch_size=0)
        with pytest.raises(ValueError, match="write_batch_size debe ser None o un entero ≥ 1"):
            validate_batch_config(chunk_size=5000, write_batch_size="invalid")

    def test_write_batch_size_none_is_valid(self) -> None:
        """write_batch_size=None es válido."""
        chunk_size, commit_cadence, write_batch = validate_batch_config(chunk_size=5000, write_batch_size=None)
        assert write_batch is None
