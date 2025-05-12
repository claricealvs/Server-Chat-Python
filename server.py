import socket
import threading
from cryptography.fernet import Fernet

chave_secreta = b'Qv5jwkrmmuZ1lgGNOYyk7UCy4dlNHkSXiRjLBNn-HHY='
fernet = Fernet(chave_secreta)

clientes_grupo = []
nicknames = {}  # conexao: nickname
clientes_privado = {}  # nickname: conexao
pares_privados = {}  # nickname: outro_nickname


def broadcast(mensagem_criptografada, remetente):
    for cliente in clientes_grupo:
        if cliente != remetente:
            try:
                cliente.sendall(mensagem_criptografada)
            except:
                cliente.close()
                if cliente in clientes_grupo:
                    clientes_grupo.remove(cliente)


def enviar_privado(destinatario_nome, mensagem_criptografada, remetente):
    destinatario = clientes_privado.get(destinatario_nome)
    if destinatario and destinatario != remetente:
        try:
            destinatario.sendall(mensagem_criptografada)
        except:
            destinatario.close()
            if destinatario_nome in clientes_privado:
                del clientes_privado[destinatario_nome]


def lidar_com_cliente(conexao, endereco):
    nickname = ""
    try:
        # Receber nickname
        while True:
            dados = conexao.recv(4096)
            mensagem = fernet.decrypt(dados).decode()
            if mensagem.startswith("NICK:"):
                nickname = mensagem.split(":", 1)[1].strip()
                if nickname in nicknames.values():
                    conexao.sendall(fernet.encrypt(b"DENIED"))
                else:
                    nicknames[conexao] = nickname
                    clientes_privado[nickname] = conexao
                    conexao.sendall(fernet.encrypt(b"OK"))
                    break

        while True:
            # Receber tipo de conversa
            cabecalho = conexao.recv(4096)
            if not cabecalho:
                break
            tipo_conversa = fernet.decrypt(cabecalho).decode().strip().lower()

            # --------------------- MODO GRUPO ---------------------
            if tipo_conversa == "grupo":
                if conexao not in clientes_grupo:
                    clientes_grupo.append(conexao)
                conexao.sendall(fernet.encrypt(b"OK"))
                print(f"[GRUPO] {nickname} entrou no chat.")

                while True:
                    dados = conexao.recv(4096)
                    if not dados:
                        return
                    mensagem = fernet.decrypt(dados).decode()

                    # Se mudar de modo
                    if mensagem.lower().startswith("privado/"):
                        break

                    print(f"[GRUPO] {mensagem}")
                    broadcast(fernet.encrypt(f"{nickname}: {mensagem}".encode()), conexao)

            # --------------------- MODO PRIVADO ---------------------
            elif tipo_conversa.startswith("privado/"):
                destinatario_nome = tipo_conversa.split("/", 1)[1].strip()

                if destinatario_nome not in clientes_privado:
                    conexao.sendall(fernet.encrypt(b"DESTINATARIO_NAO_ENCONTRADO"))
                    continue

                destinatario_con = clientes_privado[destinatario_nome]

                convite_msg = f"CONVITE:{nickname} deseja conversar em privado. Aceitar? (responda OK ou NAO)"
                destinatario_con.sendall(fernet.encrypt(convite_msg.encode()))

                resposta = fernet.decrypt(destinatario_con.recv(4096)).decode().strip().upper()
                print("[PRIVADO] recebendo resposta:", resposta)
                if resposta != "OK":
                    conexao.sendall(fernet.encrypt(b"RECUSADO"))
                    continue

                # Remover do grupo, se estiver
                if conexao in clientes_grupo:
                    clientes_grupo.remove(conexao)
                if destinatario_con in clientes_grupo:
                    clientes_grupo.remove(destinatario_con)

                # Registrar pares
                pares_privados[nickname] = destinatario_nome
                pares_privados[destinatario_nome] = nickname

                conexao.sendall(fernet.encrypt(b"OK"))
                destinatario_con.sendall(fernet.encrypt(b"OK"))
                print(f"[PRIVADO] {nickname} e {destinatario_nome} agora estão em conversa privada.")

                while True:
                    dados = conexao.recv(4096)
                    if not dados:
                        return
                    mensagem = fernet.decrypt(dados).decode()

                    # Se mudar de modo
                    if mensagem.lower() == "grupo":
                        break

                    parceiro = pares_privados.get(nickname)
                    if parceiro:
                        enviar_privado(parceiro, fernet.encrypt(f"{nickname}: {mensagem}".encode()), conexao)
                    else:
                        conexao.sendall(fernet.encrypt("Erro: parceiro não encontrado".encode()))
            else:
                conexao.sendall(fernet.encrypt(b"COMANDO_INVALIDO"))

    except Exception as e:
        print(f"Erro com cliente {endereco}: {e}")
    finally:
        conexao.close()
        if conexao in clientes_grupo:
            clientes_grupo.remove(conexao)
        if conexao in nicknames:
            print(f"[DESCONECTADO] {nicknames[conexao]} saiu do chat.")
            nome = nicknames[conexao]
            del nicknames[conexao]
            if nome in clientes_privado:
                del clientes_privado[nome]
            if nome in pares_privados:
                parceiro = pares_privados[nome]
                del pares_privados[nome]
                if parceiro in pares_privados:
                    del pares_privados[parceiro]


def main():
    host = 'localhost'
    porta = 12345

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind((host, porta))
    servidor.listen(5)
    print(f"Servidor escutando em {host}:{porta}")

    while True:
        conexao, endereco = servidor.accept()
        thread = threading.Thread(target=lidar_com_cliente, args=(conexao, endereco))
        thread.start()


if __name__ == "__main__":
    main()
