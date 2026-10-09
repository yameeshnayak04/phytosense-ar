"""Create a self-signed HTTPS certificate so phones on the same Wi-Fi can use the camera.

Browsers only allow camera access on https:// or localhost. Run:
    python scripts/make_cert.py
then start the server with run_https.cmd and open https://<your-laptop-ip>:8443 on the phone
(accept the "not secure" warning once).
"""
import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

out = Path(__file__).resolve().parent.parent / "backend" / "certs"
out.mkdir(exist_ok=True)


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


ip = local_ip()
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PhytoSense AR (dev)")])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(name).issuer_name(name)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - datetime.timedelta(days=1))
    .not_valid_after(now + datetime.timedelta(days=365))
    .add_extension(x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address(ip)),
    ]), critical=False)
    .sign(key, hashes.SHA256())
)
(out / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                                serialization.NoEncryption()))
(out / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
print(f"Certificate written to {out}")
print(f"On your phone (same Wi-Fi) open:  https://{ip}:8443")
