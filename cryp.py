from cryptography.fernet import Fernet

chave_secreta = b'Qv5jwkrmmuZ1lgGNOYyk7UCy4dlNHkSXiRjLBNn-HHY='
fernet = Fernet(chave_secreta)

def criptografar(texto):
    return fernet.encrypt(texto.encode())

def descriptografar(texto_criptografado):
    return fernet.decrypt(texto_criptografado).decode()