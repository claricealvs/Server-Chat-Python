import socket
import threading
import time
from cryptography.fernet import Fernet

# === Criptografia ===
chave_secreta = b'Qv5jwkrmmuZ1lgGNOYyk7UCy4dlNHkSXiRjLBNn-HHY='
fernet = Fernet(chave_secreta)

def criptografar(texto):
    return fernet.encrypt(texto.encode())

def descriptografar(texto_criptografado):
    return fernet.decrypt(texto_criptografado).decode()

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

def handle_client(conn, addr):
    while True:
        conn.send(criptografar("Digite seu nome de usuário: "))
        username = descriptografar(conn.recv(1024)).strip()

        if username in clients:
            conn.send(criptografar("Esse nome de usuário já está em uso. Tente outro.\n"))
        else:
            break

    clients[username] = conn
    group_chat.add(username)
    conn.send(criptografar("Bem-vindo ao chat em grupo!\n"
                           "comandos disponíveis:\n"
                           "/listar - lista todos os usuarios\n"
                           "/convite nomeusuario - manda um convite para conversa privada\n"
                           "/aceita - aceita o convite de menssagem privada\n"
                           "/sair para sair \n"))

    while True:
        try:
            msg = descriptografar(conn.recv(1024))
            if not msg:
                break

            msg = msg.strip()
            
            # Aplica rate limit (exceto para comandos importantes)
            is_command = msg.startswith("/")
            important_command = any(msg.startswith(cmd) for cmd in ["/sair", "/listar", "/aceitar"])
            
            if not (is_command and important_command):
                can_send, error_msg = check_rate_limit(username)
                if not can_send:
                    conn.send(criptografar(error_msg))
                    continue

            # Verifica se está em chat privado
            private_key = None
            for pair in private_chats:
                if username in pair:
                    private_key = pair
                    break

            if private_key:
                other_user = next(user for user in private_key if user != username)
                try:
                    clients[other_user].send(criptografar(f"[PRIVADO] {username}: {msg}"))
                except:
                    pass

                # Verifica se usuário deseja sair da conversa privada
                if msg == "/sair":
                    private_chats.pop(private_key, None)
                    group_chat.add(username)
                    group_chat.add(other_user)

                    try:
                        clients[other_user].send(criptografar(f"{username} saiu da conversa privada. Ambos voltaram ao grupo.\n"))
                    except:
                        pass

                    conn.send(criptografar("Você saiu da conversa privada e voltou para o grupo.\n"))
                continue

            if msg.startswith("/convite"):
                parts = msg.split(maxsplit=1)
                if len(parts) < 2:
                    conn.send(criptografar("Uso correto: /convite <nome_do_usuário>\n"))
                    continue
                    
                _, target = parts
                if target in group_chat and target != username:
                    invitations[target] = username
                    clients[target].send(criptografar(f"{username} convidou você para um chat privado. Digite /aceitar para entrar.\n"))
                else:
                    conn.send(criptografar("Usuário inválido ou indisponível.\n"))

            elif msg.startswith("/aceitar"):
                sender = invitations.get(username)
                if sender and sender in clients:
                    key = frozenset((username, sender))
                    private_chats[key] = (clients[username], clients[sender])
                    group_chat.discard(username)
                    group_chat.discard(sender)

                    clients[sender].send(criptografar(f"{username} aceitou seu convite. Entrando em chat privado.\n"))
                    clients[username].send(criptografar("Você entrou em chat privado.\n"))
                else:
                    conn.send(criptografar("Nenhum convite encontrado.\n"))

            elif msg.startswith("/listar"):
                user_list = "\n".join(clients.keys())
                conn.send(criptografar(f"Usuários conectados:\n{user_list}\n"))

            elif msg.startswith("/sair"):
                # Está no grupo, sai da aplicação
                conn.send(criptografar("Você saiu do grupo e desconectou da aplicação.\n"))
                clients.pop(username, None)
                group_chat.discard(username)
                break

            else:
                broadcast_group(msg, username)

        except Exception as e:
            print(f"Erro: {e}")
            break

    conn.close()
    cleanup_user(username)

def cleanup_user(username):
    """Remove o usuário de todas as estruturas de dados"""
    # Remove usuário do dicionário de clientes e do grupo
    clients.pop(username, None)
    group_chat.discard(username)
    
    # Remove dados de rate limit
    last_message_time.pop(username, None)
    rate_limit_violations.pop(username, None)
    rate_limit_timeouts.pop(username, None)

    # Remove o usuário de qualquer chat privado
    keys_to_remove = [k for k in private_chats if username in k]
    for k in keys_to_remove:
        other_user = next(user for user in k if user != username)
        try:
            clients[other_user].send(criptografar(f"{username} saiu do chat privado (desconectado). Você voltou ao grupo.\n"))
        except:
            pass
        group_chat.add(other_user)
        del private_chats[k]

    print(f"{username} desconectado")


def start():
    host = 'localhost'
    port = 12345
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    print(f"Servidor ouvindo em {host}:{port}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    try:
        start()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")