"""Genera una CA y un certificado de servidor de pruebas para el MariaDB del banco (TLS con verificación).

Solo para el banco local: las claves se escriben en ``build/bench_tls/`` (ignorado por git) y no protegen nada real.
El certificado de servidor solo tiene ``IP:127.0.0.1`` en el SAN: conectar como ``127.0.0.1`` verifica, conectar como
``localhost`` debe fallar la comprobación del hostname.

Uso::

    python scripts/bench_tls_certs.py
    docker compose -f docker-compose.bench.yml -f docker-compose.bench-tls.yml up -d --wait --force-recreate -V mariadb

``--force-recreate -V`` borra los datos del contenedor MariaDB (los vuelve a crear los tests). Después,
``ssl_ca=build/bench_tls/ca.pem`` en los ``conn_params`` de MariaDB.
"""

from __future__ import annotations

import argparse
import datetime
import ipaddress

from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


class BenchTlsCertificates:
    """CA y certificado de servidor autofirmados para el banco de pruebas."""

    VALID_DAYS: int = 825

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir

    @staticmethod
    def _key() -> rsa.RSAPrivateKey:
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)

    @staticmethod
    def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
        path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )

    def generate(self) -> list[Path]:
        """Escribe ``ca.pem``, ``ca-key.pem``, ``server-cert.pem`` y ``server-key.pem``; devuelve sus rutas."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now(datetime.UTC)
        until = now + datetime.timedelta(days=self.VALID_DAYS)

        ca_key = self._key()
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "util_bbdd bench CA")])
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(until)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256())
        )

        server_key = self._key()
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "util_bbdd bench mariadb")]))
            .issuer_name(ca_name)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(until)
            .add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False
            )
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        paths = {
            "ca.pem": ca_cert.public_bytes(serialization.Encoding.PEM),
            "server-cert.pem": server_cert.public_bytes(serialization.Encoding.PEM),
        }
        for name, data in paths.items():
            (self.out_dir / name).write_bytes(data)
        self._write_key(self.out_dir / "ca-key.pem", ca_key)
        self._write_key(self.out_dir / "server-key.pem", server_key)
        return [self.out_dir / name for name in ("ca.pem", "ca-key.pem", "server-cert.pem", "server-key.pem")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("build/bench_tls"), help="Directorio de salida")
    args = parser.parse_args()
    for path in BenchTlsCertificates(args.out).generate():
        print(path)


if __name__ == "__main__":
    main()
