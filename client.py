import socket
import threading
from cryptography.fernet import Fernet

# === Criptografia ===
chave_secreta = b'Qv5jwkrmmuZ1lgGNOYyk7UCy4dlNHkSXiRjLBNn-HHY='
fernet = Fernet(chave_secreta)

def criptografar(texto):
    return fernet.encrypt(texto.encode())

def descriptografar(texto_criptografado):
    return fernet.decrypt(texto_criptografado).decode()

def receive_messages(sock):
    while True:
        try:
            msg_criptografada = sock.recv(1024)
            if msg_criptografada:
                msg = descriptografar(msg_criptografada)
                print(msg)
            else:
                break
        except:
            break

def start():
    host = '127.0.0.1'
    port = 5555
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    while True:
        try:
            msg = input()
            sock.send(criptografar(msg))
        except:
            break

if __name__ == "__main__":
    start()
