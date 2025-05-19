import os

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta

CERT_FILE = "certificado.crt"
KEY_FILE = "chave.key"

def gerar_certificado_se_necessario():
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        print("Certificado SSL não encontrado. Gerando automaticamente...")

        # Gera chave privada
        chave = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Define informações do certificado
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "SP"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Sao Paulo"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MeuServidor"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        certificado = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            chave.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False
        ).sign(chave, hashes.SHA256())

        # Salva a chave privada
        with open(KEY_FILE, "wb") as f:
            f.write(chave.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # Salva o certificado
        with open(CERT_FILE, "wb") as f:
            f.write(certificado.public_bytes(serialization.Encoding.PEM))

        print("Certificado e chave gerados com sucesso.")
