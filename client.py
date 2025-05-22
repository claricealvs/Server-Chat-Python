import socket
import threading
import time
import ssl
from cryptography.fernet import Fernet

def start_cliente(id_cliente):
    fernet = None

    def criptografar(texto):
        return fernet.encrypt(texto.encode())

    def descriptografar(texto_criptografado):
        return fernet.decrypt(texto_criptografado).decode()

    HOST = '192.168.0.104'
    PORT = 5556

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        context = ssl._create_unverified_context()

        sock = context.wrap_socket(sock, server_hostname=HOST)
        sock.connect((HOST, PORT))

        print(f"[CLIENTE {id_cliente}] Conectado ao servidor via SSL")

        chave_recebida = sock.recv(1024).strip()
        fernet = Fernet(chave_recebida)

        nickname = f"bot{id_cliente}"
        sock.send(fernet.encrypt(nickname.encode()))
        print(f"[CLIENTE {id_cliente}] Nickname '{nickname}' enviado.")

        # Thread para receber mensagens
        def receber():
            while True:
                try:
                    data = sock.recv(1024)
                    if not data:
                        print(f"[CLIENTE {id_cliente}] Conexão encerrada pelo servidor.")
                        break
                    decrypted_msg = descriptografar(data)
                    print(f"[CLIENTE {id_cliente}] Servidor: {decrypted_msg}")
                except Exception as e:
                    print(f"[CLIENTE {id_cliente}] Erro ao receber: {e}")
                    break

        threading.Thread(target=receber, daemon=True).start()

        for i in range(5):
            mensagem = f"Olá do cliente {id_cliente} - msg {i}"
            encrypted = criptografar(mensagem)
            sock.send(encrypted)
            print(f"[CLIENTE {id_cliente}] Mensagem enviada: {mensagem}")
            time.sleep(1)

        sock.close()
        print(f"[CLIENTE {id_cliente}] Desconectado")

    except Exception as e:
        print(f"[CLIENTE {id_cliente}] Falha na conexão: {e}")

# Cria múltiplas conexões
def criar_multiplas_conexoes(qtd):
    for i in range(qtd):
        threading.Thread(target=start_cliente, args=(i,), daemon=True).start()
        time.sleep(0.5)

if _name_ == "_main_":
    criar_multiplas_conexoes(1000)
    time.sleep(30)