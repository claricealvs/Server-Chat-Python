import socket
import threading
import time
from cryptography.fernet import Fernet
import ssl

from client import fernet
from cryp import gerar_certificado_se_necessario

# === Criptografia ===
fernetKey = Fernet.generate_key()
fernet = Fernet(fernetKey)


def criptografar(msg):
    return fernet.encrypt(msg.encode())


def descriptografar(msg):
    return fernet.decrypt(msg).decode()


# === Estruturas de dados ===
clients = {}  # username -> conn
group_chat = set()  # usernames
private_chats = {}  # frozenset([user1, user2]) -> (conn1, conn2)
invitations = {}  # receiver -> sender
historico_grupo = []
def broadcast_group(message, sender):
    texto = f"[GRUPO] {sender}: {message}"
    historico_grupo.append(texto)
    for user in group_chat:
        if user != sender:
            try:
                clients[user].send(criptografar(texto))
            except:
                pass


def handle_client(conn, addr):
    if not enviar_chave_fernet(conn, addr):
        return

    username = autenticar_usuario(conn)
    if not username:
        conn.close()
        return

    clients[username] = conn
    group_chat.add(username)
    enviar_mensagem_inicial(conn)

    max_msgs = 5
    intervalo = 10  # segundos
    historico_msgs = []

    while True:
        try:
            if not check_rate_limit(historico_msgs, max_msgs, intervalo, username, conn):
                break  # Cliente foi desconectado por flood

            raw = conn.recv(1024)
            if not raw:
                break
            msg = descriptografar(raw).strip()

            historico_msgs.append(time.time())

            if processar_comando(msg, username, conn):
                continue
            broadcast_group(msg, username)

        except Exception as e:
            print(f"Erro com o cliente {username}: {e}")
            break

    encerrar_conexao(username, conn)


def check_rate_limit(historico_msgs, max_msgs, intervalo, username, conn):
    """Verifica se o cliente passou do limite de mensagens. Retorna True se pode continuar, False se deve ser desconectado."""
    agora = time.time()
    historico_msgs[:] = [t for t in historico_msgs if agora - t < intervalo]

    if len(historico_msgs) >= max_msgs:
        msg = "Você foi desconectado por enviar muitas mensagens em pouco tempo."
        conn.send(criptografar(msg))
        broadcast_group(f"{username} foi desconectado por enviar muitas mensagens em pouco tempo.", "system")
        print(f"[LOG] {username} foi desconectado por enviar muitas mensagens em pouco tempo.")
        return False

    return True


def enviar_chave_fernet(conn, addr):
    try:
        conn.send(fernetKey + b'\n')
        return True
    except Exception as e:
        print(f"Erro ao enviar chave para {addr}: {e}")
        conn.close()
        return False


def autenticar_usuario(conn):
    while True:
        conn.send(criptografar("Digite seu nome de usuário (sem espaços): "))
        username = descriptografar(conn.recv(1024)).strip()

        # Verifica se o nome de usuário contém espaços
        if " " in username:
            conn.send(criptografar("O nome de usuário não pode conter espaços. Tente novamente.\n"))
            continue

        if username in clients:
            conn.send(criptografar("Esse nome de usuário já está em uso. Tente outro.\n"))
        else:
            print(f"[LOG] Usuário conectado: {username}")
            return username


def enviar_mensagem_inicial(conn):
    conn.send(criptografar("Bem-vindo ao chat em grupo!\nDigite /help para ver os comandos disponíveis.\n"))
    if historico_grupo:
        conn.send(criptografar("\n--- Histórico do grupo ---\n"))
        for linha in historico_grupo[-20:]:  # mostra as últimas 20 mensagens
            conn.send(criptografar(linha))
        conn.send(criptografar("\n---------------------------\n"))



def enviar_comandos_disponiveis(conn):
    comandos = (
        "/listar - Lista todos os usuários conectados\n"
        "/convite <nome> - Envia convite para chat privado\n"
        "/aceitar - Aceita um convite de chat privado\n"
        "/historico - Exibe todas as mensagens trocadas no grupo\n"
        "/sair - Sai do chat (grupo ou privado)\n"
        "/help - Mostra esta mensagem de ajuda\n"
    )
    conn.send(criptografar(comandos))


def processar_comando(msg, username, conn):
    # Verifica se está em chat privado
    private_key = next((pair for pair in private_chats if username in pair), None)

    if private_key:
        other_user = next(user for user in private_key if user != username)

        # Comando para sair da conversa privada
        if msg == "/sair":
            private_chats.pop(private_key, None)
            group_chat.update([username, other_user])
            try:
                clients[other_user].send(
                    criptografar(f"{username} saiu da conversa privada. Ambos voltaram ao grupo.\n"))
            except:
                pass
            conn.send(criptografar("Você saiu da conversa privada e voltou para o grupo.\n"))
            print(f"[LOG] {username} saiu da conversa privada com {other_user}")
            return True

        # Caso contrário, envia a mensagem normalmente
        try:
            print(msg)
            clients[other_user].send(criptografar(f"[PRIVADO] {username}: {msg}"))
        except:
            pass

        return True

    if msg.startswith("/convite"):
        partes = msg.split(maxsplit=1)
        if len(partes) < 2:
            conn.send(criptografar("Uso: /convite <nomeusuario>\n"))
            return True
        target = partes[1]
        if target in group_chat and target != username:
            invitations[target] = username
            clients[target].send(
                criptografar(f"{username} convidou você para um chat privado. Digite /aceitar para entrar.\n"))
        else:
            conn.send(criptografar("Usuário inválido ou indisponível.\n"))
        return True

    elif msg.startswith("/aceitar"):
        sender = invitations.get(username)
        if sender and sender in clients:
            key = frozenset((username, sender))
            private_chats[key] = (clients[username], clients[sender])
            group_chat.difference_update({username, sender})
            clients[sender].send(criptografar(f"{username} aceitou seu convite. Entrando em chat privado.\n"))
            conn.send(criptografar("Você entrou em chat privado.\n"))

            print(f"[LOG] Conversa privada iniciada entre {username} e {sender}")
        else:
            conn.send(criptografar("Nenhum convite encontrado.\n"))
        return True


    elif msg.startswith("/listar"):
        user_list = "\n".join(clients.keys())
        conn.send(criptografar(f"Usuários conectados:\n{user_list}\n"))
        return True

    elif msg.startswith("/historico"):
        if historico_grupo:
            conn.send(criptografar("\n--- Histórico do grupo ---\n"))
            for linha in historico_grupo:
                conn.send(criptografar(linha))
            conn.send(criptografar("\n---------------------------\n"))
        else:
            conn.send(criptografar("Ainda não há mensagens no grupo.\n"))
        return True


    elif msg.startswith("/sair"):
        conn.send(criptografar("Você saiu do grupo e desconectou da aplicação.\n"))
        clients.pop(username, None)
        group_chat.discard(username)
        conn.close()
        return True

    elif msg.startswith("/help"):
        enviar_comandos_disponiveis(conn)
        return True

    return False


def encerrar_conexao(username, conn):
    conn.close()
    clients.pop(username, None)
    group_chat.discard(username)

    # Remove de chats privados
    for k in [k for k in private_chats if username in k]:
        other_user = next(user for user in k if user != username)
        try:
            clients[other_user].send(
                criptografar(f"{username} saiu do chat privado (desconectado). Você voltou ao grupo.\n"))
        except:
            pass
        group_chat.add(other_user)
        private_chats.pop(k)

    print(f"{username} desconectado")


def start():
    host = "10.44.52.102"
    port = 5546

    gerar_certificado_se_necessario()
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="certificado.crt", keyfile="chave.key")

    raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_socket.bind((host, port))
    raw_socket.listen()
    print(f"Servidor seguro ouvindo em {host}:{port} (TLS habilitado)")

    while True:
        conn, addr = raw_socket.accept()
        try:
            secure_conn = context.wrap_socket(conn, server_side=True)
            threading.Thread(target=handle_client, args=(secure_conn, addr), daemon=True).start()
        except ssl.SSLError as e:
            print(f"Erro SSL com {addr}: {e}")


if __name__ == "__main__":
    try:
        start()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
