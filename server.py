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

# === Estruturas de dados ===
clients = {}  # username -> conn
group_chat = set()  # usernames
private_chats = {}  # frozenset([user1, user2]) -> (conn1, conn2)
invitations = {}  # receiver -> sender

def broadcast_group(message, sender):
    for user in group_chat:
        if user != sender:
            try:
                clients[user].send(criptografar(f"[GRUPO] {sender}: {message}"))
            except:
                pass

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
                _, target = msg.split(maxsplit=1)
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

        except:
            break

    conn.close()
    del clients[username]
    group_chat.discard(username)

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
    host = '192.168.0.100'
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
