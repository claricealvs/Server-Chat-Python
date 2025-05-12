import socket
import threading
from cryptography.fernet import Fernet

chave_secreta = b'Qv5jwkrmmuZ1lgGNOYyk7UCy4dlNHkSXiRjLBNn-HHY='
fernet = Fernet(chave_secreta)

nickname = ""
modo_privado = False
parceiro_privado = ""

def receber_mensagens(cliente):
    global modo_privado, parceiro_privado
    while True:
        try:
            dados = cliente.recv(4096)
            if not dados:
                print("Conexão encerrada pelo servidor.")
                break
            mensagem = fernet.decrypt(dados).decode()

            if mensagem.startswith("CONVITE:"):
                print(f"\n{mensagem}")
                remetente = mensagem.split(":")[1].split()[0]  # extrai o nickname do remetente
                while True:
                    resposta = input("Digite 'OK' para aceitar ou 'NAO' para recusar: ").strip().upper()
                    if resposta in ["OK", "NAO"]:
                        cliente.sendall(fernet.encrypt(resposta.encode()))
                        if resposta == "OK":
                            modo_privado = True
                            parceiro_privado = remetente
                            print(f"[DEBUG] Conversa privada com {parceiro_privado} iniciada.")
                        break

            elif mensagem == "RECUSADO":
                print("Convite recusado pelo destinatário.")
            elif mensagem == "DESTINATARIO_NAO_ENCONTRADO":
                print("Usuário destinatário não encontrado.")
            elif mensagem == "Erro: parceiro não encontrado":
                print("Erro: parceiro não encontrado.")
            else:
                print(f"\n{mensagem}")
        except Exception as e:
            print("Erro ao receber/descriptografar:", e)
            break


def main():
    global nickname, modo_privado, parceiro_privado
    host = 'localhost'
    porta = 12345

    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("[DEBUG] Tentando conectar ao servidor...")
        cliente.connect((host, porta))
        print("[DEBUG] Conectado com sucesso ao servidor!")

        # Solicita e envia nickname
        while True:
            nickname = input("Escolha seu nickname: ").strip()
            cliente.sendall(fernet.encrypt(f"NICK:{nickname}".encode()))

            resposta_nick = cliente.recv(4096)
            resposta_nick_decifrada = fernet.decrypt(resposta_nick).decode()

            if resposta_nick_decifrada == "OK":
                print("[DEBUG] Nickname aceito.")
                break
            else:
                print("[DEBUG] Nickname já em uso. Tente outro.")

        while True:
            escolha = input("Você deseja conversar em [grupo] ou [privado]? ").strip().lower()

            if escolha == "grupo":
                cliente.sendall(fernet.encrypt(b"grupo"))
                modo_privado = False
            elif escolha == "privado":
                parceiro_privado = input("Digite o nickname do usuário com quem deseja conversar: ").strip()
                cliente.sendall(fernet.encrypt(f"privado/{parceiro_privado}".encode()))
                modo_privado = True
            else:
                print("Opção inválida. Digite 'grupo' ou 'privado'.")
                continue

            resposta = cliente.recv(4096)
            resposta_decifrada = fernet.decrypt(resposta).decode()

            if resposta_decifrada == "OK":
                print("[DEBUG] Acesso permitido à conversa.")
                break
            elif resposta_decifrada == "RECUSADO":
                print("O destinatário recusou a conversa privada.")
                return
            elif resposta_decifrada == "DESTINATARIO_NAO_ENCONTRADO":
                print("Destinatário não encontrado.")
                return
            else:
                print("[DEBUG] Servidor recusou a opção. Tente novamente.")

        threading.Thread(target=receber_mensagens, args=(cliente,), daemon=True).start()

        while True:
            mensagem = input("Você: ").strip()
            if not mensagem:
                continue

            if modo_privado and parceiro_privado:
                mensagem_formatada = f"{parceiro_privado}: {mensagem}"
            else:
                mensagem_formatada = f"{nickname}: {mensagem}"

            cliente.sendall(fernet.encrypt(mensagem_formatada.encode()))

    except Exception as e:
        print("Erro ao conectar ou durante a comunicação:", e)

if __name__ == "__main__":
    main()
