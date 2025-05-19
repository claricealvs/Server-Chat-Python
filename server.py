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

# === Rate limit ===
last_message_time = {}  # username -> timestamp da última mensagem
rate_limit_window = 0.5  # intervalo mínimo entre mensagens (em segundos)
rate_limit_max_violations = 3  # número máximo de violações antes de aplicar timeout
rate_limit_violations = {}  # username -> contagem de violações
rate_limit_timeouts = {}  # username -> timestamp de quando o timeout expira

def broadcast_group(message, sender):
    for user in group_chat:
        if user != sender:
            try:
                clients[user].send(criptografar(f"[GRUPO] {sender}: {message}"))
            except:
                pass

def check_rate_limit(username):
    """
    Verifica se o usuário está dentro do rate limit
    Retorna True se a mensagem pode ser processada, False caso contrário
    """
    current_time = time.time()
    
    # Verifica se o usuário está em timeout
    if username in rate_limit_timeouts:
        timeout_until = rate_limit_timeouts[username]
        if current_time < timeout_until:
            remaining = round(timeout_until - current_time, 1)
            return False, f"Você está enviando mensagens muito rapidamente. Aguarde mais {remaining} segundos."
        else:
            # Timeout expirou, remove o registro
            del rate_limit_timeouts[username]
            rate_limit_violations[username] = 0
    
    # Verifica intervalo entre mensagens
    if username in last_message_time:
        time_since_last_msg = current_time - last_message_time[username]
        if time_since_last_msg < rate_limit_window:
            # Incrementa contador de violações
            if username not in rate_limit_violations:
                rate_limit_violations[username] = 1
            else:
                rate_limit_violations[username] += 1
            
            # Se excedeu o limite de violações, aplica timeout
            if rate_limit_violations[username] >= rate_limit_max_violations:
                # Timeout progressivo: 3s, 5s, 10s, etc. (máximo de 30s)
                timeout_duration = min(3 * (2 ** (rate_limit_violations[username] - rate_limit_max_violations)), 30)
                rate_limit_timeouts[username] = current_time + timeout_duration
                return False, f"Rate limit excedido! Timeout de {timeout_duration} segundos aplicado."
            
            return False, "Aguarde um momento antes de enviar outra mensagem."
    
    # Atualiza timestamp da última mensagem
    last_message_time[username] = current_time
    return True, None

import time

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

    # === Controle de flood: 5 mensagens por 10 segundos ===
    max_msgs = 5
    intervalo = 10  # segundos
    historico_msgs = []

    while True:
        try:
            # Limpa o histórico antigo
            agora = time.time()
            historico_msgs = [t for t in historico_msgs if agora - t < intervalo]

            # Verifica se passou do limite
            if len(historico_msgs) >= max_msgs:
                conn.send(criptografar("Você foi desconectado por enviar muitas mensagens em pouco tempo."))
                broadcast_group(f"{username} foi desconectado por enviar muitas mensagens em pouco tempo.","system")
                print(f"[LOG] {username} foi desconectado por enviar muitas mensagens em pouco tempo.")
                break  # Desconecta o cliente

            # Recebe mensagem
            raw = conn.recv(1024)
            if not raw:
                break
            msg = descriptografar(raw).strip()

            historico_msgs.append(agora)

            if processar_comando(msg, username, conn):
                continue
            broadcast_group(msg, username)

        except Exception as e:
            print(f"Erro com o cliente {username}: {e}")
            break

    encerrar_conexao(username, conn)


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
    conn.send(criptografar("Bem-vindo ao chat em grupo!\n"
                           "Digite /help para ver os comandos disponíveis.\n"))


def enviar_comandos_disponiveis(conn):
    comandos = (
        "/listar - Lista todos os usuários conectados\n"
        "/convite <nome> - Envia convite para chat privado\n"
        "/aceitar - Aceita um convite de chat privado\n"
        "/sair - Sai do chat (grupo ou privado)\n"
        "/help - Mostra esta mensagem de ajuda\n"
    )
    conn.send(criptografar(comandos))


def processar_comando(msg, username, conn):
    # Verifica se está em chat privado
    private_key = next((pair for pair in private_chats if username in pair), None)

    if private_key:
        other_user = next(user for user in private_key if user != username)
        try:
            clients[other_user].send(criptografar(f"[PRIVADO] {username}: {msg}"))
        except:
            pass

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

    if msg.startswith("/convite"):
        partes = msg.split(maxsplit=1)
        if len(partes) < 2:
            conn.send(criptografar("Uso: /convite <nomeusuario>\n"))
            return True
        target = partes[1]
        if target in group_chat and target != username:
            invitations[target] = username
            clients[target].send(criptografar(f"{username} convidou você para um chat privado. Digite /aceitar para entrar.\n"))
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
            clients[other_user].send(criptografar(f"{username} saiu do chat privado (desconectado). Você voltou ao grupo.\n"))
        except:
            pass
        group_chat.add(other_user)
        private_chats.pop(k)

    print(f"{username} desconectado")



def start():
    host = 'localhost'
    port = 5556

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