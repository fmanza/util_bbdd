"""P1 de drivers-connections-audit (FASE 1, 2026-10-08): TLS de MySQL en los caminos sync y async.

- **Y3**: ``build_aiomysql_connect_kwargs`` descartaba ``ssl_*`` (aiomysql solo acepta ``ssl=SSLContext``), así que la
  conexión async iba en claro aunque se configurara TLS.
- **Sync**: ``build_pymysql_connect_kwargs`` metía CA/cert/key en ``ssl`` pero dejaba ``ssl_verify_cert`` /
  ``ssl_verify_identity`` como kwargs sueltos; si alguno era verdadero, PyMySQL rehacía ``ssl`` con ``ca=None`` y se
  perdían la CA y el certificado de cliente.
"""

from __future__ import annotations

import datetime
import ssl

from pathlib import Path
from typing import Any

import pytest

from util_bbdd.connection.mysql.async_connection_mysql import build_aiomysql_connect_kwargs
from util_bbdd.connection.mysql.connection_mysql import build_pymysql_connect_kwargs

BASE: dict[str, Any] = {"host": "db", "user": "app", "password": "pw", "database": "sales"}
CA_NAME = "util-bbdd-test-ca"


@pytest.fixture(scope="module")
def ca_file(tmp_path_factory: pytest.TempPathFactory) -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_NAME)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    path: Path = tmp_path_factory.mktemp("tls") / "ca.pem"
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(path)


def _ca_names(ctx: ssl.SSLContext) -> list[str]:
    return [
        value for cert in ctx.get_ca_certs() for rdn in cert["subject"] for key, value in rdn if key == "commonName"
    ]


def test_pymysql_kwargs_keep_verification_inside_ssl_dict() -> None:
    kwargs = build_pymysql_connect_kwargs(
        {**BASE, "ssl_ca": "/ca", "ssl_key": "/k", "ssl_verify_cert": True, "ssl_verify_identity": False}
    )

    assert kwargs["ssl"] == {"ca": "/ca", "key": "/k", "verify_mode": True, "check_hostname": False}
    assert not {"ssl_ca", "ssl_key", "ssl_verify_cert", "ssl_verify_identity"} & set(kwargs)


def test_pymysql_connection_keeps_ca_when_verify_cert_is_true(ca_file: str) -> None:
    import pymysql

    kwargs = build_pymysql_connect_kwargs({**BASE, "ssl_ca": ca_file, "ssl_verify_cert": True})
    conn = pymysql.connections.Connection(defer_connect=True, **kwargs)

    assert conn.ctx.verify_mode == ssl.CERT_REQUIRED
    assert CA_NAME in _ca_names(conn.ctx)


def test_aiomysql_kwargs_build_ssl_context_from_tls_params(ca_file: str) -> None:
    aiomysql = pytest.importorskip("aiomysql")

    kwargs = build_aiomysql_connect_kwargs({**BASE, "ssl_ca": ca_file}, aiomysql.connect)
    ctx = kwargs["ssl"]

    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert CA_NAME in _ca_names(ctx)
    assert not any(key.startswith("ssl_") for key in kwargs)


def test_aiomysql_kwargs_honour_disabled_verification(ca_file: str) -> None:
    aiomysql = pytest.importorskip("aiomysql")

    kwargs = build_aiomysql_connect_kwargs(
        {**BASE, "ssl_ca": ca_file, "ssl_verify_cert": False, "ssl_verify_identity": False}, aiomysql.connect
    )

    assert kwargs["ssl"].verify_mode == ssl.CERT_NONE
    assert kwargs["ssl"].check_hostname is False


def test_aiomysql_kwargs_without_tls_have_no_ssl() -> None:
    aiomysql = pytest.importorskip("aiomysql")

    assert "ssl" not in build_aiomysql_connect_kwargs(dict(BASE), aiomysql.connect)
