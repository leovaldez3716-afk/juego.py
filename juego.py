import pygame
import pgzrun
import random
import math
from collections import deque

WIDTH = 720
HEIGHT = 720
TITLE = "Labirinto - Miranha"

TAMANHO_PERSONAGEM = 18
RAIO_JOGADOR = 5
RAIO_INIMIGO = 5
RAIO_COIN = 4

VELOCIDADE_JOGADOR = 110
VELOCIDADE_DASH = 420
DASH_DURACAO = 0.15
DASH_COOLDOWN = 3.0

# ---------- inimigo / IA ----------
VELOCIDADE_INIMIGO_PATRULHA = 55   # andando "sem saber" onde o jogador esta
VELOCIDADE_INIMIGO_PERSEGUE = 88   # perseguindo (ainda menor que o jogador: 110)

RAIO_VISAO = 330           # enxerga o jogador ate essa distancia SE nao houver parede no meio
RAIO_AUDICAO = 64          # "ouve" o jogador mesmo atras da parede, se estiver muito perto
MEMORIA_PERSEGUICAO = 4.0  # segundos que continua procurando depois de perder o jogador de vista
INIMIGO_SEMPRE_SABE = False  # True = o inimigo SEMPRE sabe onde o jogador esta (labirinto inteiro)

TEMPO_RECALCULO = 0.2      # recalcula o BFS a cada 0.2s

PASSO_MAX = 2

PONTOS_PARA_VENCER = 7

# ---------- estado do jogo ----------
# MENU -> JOGANDO -> (PAUSADO <-> JOGANDO) -> GAMEOVER ou VITORIA
pontos = 0
vidas = 3
estado_jogo = "MENU"

anim_timer = 0
ANIM_COOLDOWN = 0.15

dash_ativo = False
dash_tempo_restante = 0
dash_cooldown_restante = 0
dash_dir_x = 0
dash_dir_y = 0
direcao_atual_x = 0
direcao_atual_y = 1

labirinto_img = images.labirinto

OFF_X = (WIDTH - labirinto_img.get_width()) // 2
OFF_Y = (HEIGHT - labirinto_img.get_height()) // 2


def redimensionar(ator, altura):
    escala = altura / ator.height
    novo = pygame.transform.smoothscale(
        ator._orig_surf, (int(ator.width * escala), altura))
    ator._orig_surf = ator._surf = novo
    ator._update_pos()


def ponto_e_parede(x, y):
    """Funciona tanto se a imagem tiver transparencia de verdade quanto se
    tiver sido 'achatada' (fundo branco opaco + linhas escuras)."""
    ix = int(x - OFF_X)
    iy = int(y - OFF_Y)

    if ix < 0 or iy < 0 or ix >= labirinto_img.get_width() or iy >= labirinto_img.get_height():
        return True

    r, g, b, a = labirinto_img.get_at((ix, iy))

    if a < 127:
        return False

    brilho = (r + g + b) / 3
    return brilho < 150


def circulo_colide(x, y, raio):
    pontos_teste = [
        (x, y),
        (x - raio, y), (x + raio, y),
        (x, y - raio), (x, y + raio),
        (x - raio * 0.7, y - raio * 0.7), (x + raio * 0.7, y - raio * 0.7),
        (x - raio * 0.7, y + raio * 0.7), (x + raio * 0.7, y + raio * 0.7),
    ]
    for px, py in pontos_teste:
        if ponto_e_parede(px, py):
            return True
    return False


def mover_com_colisao(x, y, dx, dy, raio):
    distancia = math.hypot(dx, dy)
    if distancia == 0:
        return x, y

    passos = max(1, int(distancia / PASSO_MAX))
    passo_x = dx / passos
    passo_y = dy / passos

    for _ in range(passos):
        novo_x = x + passo_x
        if not circulo_colide(novo_x, y, raio):
            x = novo_x

        novo_y = y + passo_y
        if not circulo_colide(x, novo_y, raio):
            y = novo_y

    return x, y


# =====================================================================
#  GRAFO DO LABIRINTO (cada celula livre = no; vizinhas sem parede = aresta)
#  CELL_SIZE = 16 combina com o labirinto.png gerado (blocos de 16px)
# =====================================================================
CELL_SIZE = 16
COLS = labirinto_img.get_width() // CELL_SIZE
ROWS = labirinto_img.get_height() // CELL_SIZE


def celula_para_pos(col, lin):
    x = OFF_X + col * CELL_SIZE + CELL_SIZE / 2
    y = OFF_Y + lin * CELL_SIZE + CELL_SIZE / 2
    return x, y


def celula_livre(col, lin):
    x, y = celula_para_pos(col, lin)
    return not ponto_e_parede(x, y)


def pos_para_celula(x, y):
    col = int((x - OFF_X) // CELL_SIZE)
    lin = int((y - OFF_Y) // CELL_SIZE)
    col = max(0, min(COLS - 1, col))
    lin = max(0, min(ROWS - 1, lin))
    return col, lin


def construir_grafo():
    livre = {}
    for lin in range(ROWS):
        for col in range(COLS):
            livre[(col, lin)] = celula_livre(col, lin)

    grafo = {}
    for lin in range(ROWS):
        for col in range(COLS):
            if not livre[(col, lin)]:
                continue
            vizinhos = []
            for dcol, dlin in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                vcol, vlin = col + dcol, lin + dlin
                if 0 <= vcol < COLS and 0 <= vlin < ROWS and livre[(vcol, vlin)]:
                    x1, y1 = celula_para_pos(col, lin)
                    x2, y2 = celula_para_pos(vcol, vlin)
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    if not ponto_e_parede(mx, my):
                        vizinhos.append((vcol, vlin))
            grafo[(col, lin)] = vizinhos
    return grafo


GRAFO_LABIRINTO = construir_grafo()
CELULAS_LIVRES = list(GRAFO_LABIRINTO.keys())


def bfs_caminho(grafo, origem, destino):
    """Busca em Largura: caminho mais curto de 'origem' ate 'destino'.
    Retorna lista de celulas (sem a origem) ou None se nao houver caminho."""
    if origem not in grafo or destino not in grafo:
        return None
    if origem == destino:
        return []

    visitados = {origem: None}
    fila = deque([origem])

    while fila:
        atual = fila.popleft()
        if atual == destino:
            break
        for vizinho in grafo[atual]:
            if vizinho not in visitados:
                visitados[vizinho] = atual
                fila.append(vizinho)

    if destino not in visitados:
        return None

    caminho = []
    atual = destino
    while atual != origem:
        caminho.append(atual)
        atual = visitados[atual]
    caminho.reverse()
    return caminho


def posicao_livre_aleatoria(raio, pos_evitar=None, dist_minima=100):
    """Sorteia o CENTRO de uma celula livre (sempre no meio do corredor)."""
    for _ in range(3000):
        col, lin = random.choice(CELULAS_LIVRES)
        x, y = celula_para_pos(col, lin)
        if pos_evitar is not None:
            if math.hypot(x - pos_evitar[0], y - pos_evitar[1]) < dist_minima:
                continue
        return x, y

    print("AVISO: nao achei posicao livre no labirinto!")
    x, y = celula_para_pos(*CELULAS_LIVRES[0])
    return x, y


# =====================================================================
#  IA DO INIMIGO: PATRULHA -> PERSEGUINDO (percebeu) -> PATRULHA
# =====================================================================
def tem_linha_de_visao(x1, y1, x2, y2):
    """Lanca um 'raio' de (x1,y1) ate (x2,y2). Se cruzar parede, nao ve."""
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist == 0:
        return True
    passos = int(dist / 4) + 1
    for i in range(1, passos):
        t = i / passos
        if ponto_e_parede(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
            return False
    return True


def inimigo_percebe_jogador():
    if INIMIGO_SEMPRE_SABE:
        return True
    dist = math.hypot(miranha.x - inimigo.x, miranha.y - inimigo.y)
    if dist <= RAIO_AUDICAO:
        return True  # ouviu
    if dist <= RAIO_VISAO and tem_linha_de_visao(inimigo.x, inimigo.y, miranha.x, miranha.y):
        return True  # viu
    return False


miranha = Actor("sprite3")
redimensionar(miranha, TAMANHO_PERSONAGEM)

coin = Actor("coin")
redimensionar(coin, TAMANHO_PERSONAGEM - 6)

inimigo = Actor("inimigo")
redimensionar(inimigo, TAMANHO_PERSONAGEM)

ia_estado = "PATRULHA"          # "PATRULHA" ou "PERSEGUINDO"
caminho_inimigo = []
tempo_recalculo_caminho = 0
ultima_celula_jogador = None    # ultimo lugar onde o inimigo percebeu o jogador
tempo_sem_perceber = 0


def resetar_posicoes():
    global dash_ativo, dash_cooldown_restante, caminho_inimigo, tempo_recalculo_caminho
    global ia_estado, ultima_celula_jogador, tempo_sem_perceber
    miranha.x, miranha.y = posicao_livre_aleatoria(RAIO_JOGADOR)
    inimigo.x, inimigo.y = posicao_livre_aleatoria(RAIO_INIMIGO, pos_evitar=(miranha.x, miranha.y), dist_minima=250)
    coin.x, coin.y = posicao_livre_aleatoria(RAIO_COIN, pos_evitar=(miranha.x, miranha.y), dist_minima=80)

    ia_estado = "PATRULHA"
    caminho_inimigo = []
    tempo_recalculo_caminho = 0
    ultima_celula_jogador = None
    tempo_sem_perceber = 0
    dash_ativo = False
    dash_cooldown_restante = 0


def reiniciar_jogo_completo():
    global pontos, vidas, estado_jogo
    pontos = 0
    vidas = 3
    estado_jogo = "JOGANDO"
    resetar_posicoes()


def atualizar_ia_inimigo(dt):
    global ia_estado, caminho_inimigo, tempo_recalculo_caminho
    global ultima_celula_jogador, tempo_sem_perceber

    percebeu = inimigo_percebe_jogador()
    celula_inimigo = pos_para_celula(inimigo.x, inimigo.y)

    if percebeu:
        ia_estado = "PERSEGUINDO"
        tempo_sem_perceber = 0
        ultima_celula_jogador = pos_para_celula(miranha.x, miranha.y)
    elif ia_estado == "PERSEGUINDO":
        tempo_sem_perceber += dt
        chegou_no_ultimo_lugar = (celula_inimigo == ultima_celula_jogador)
        if tempo_sem_perceber > MEMORIA_PERSEGUICAO or chegou_no_ultimo_lugar:
            ia_estado = "PATRULHA"       # desistiu, volta a vasculhar o labirinto
            caminho_inimigo = []

    # --- decide o caminho (BFS) ---
    if ia_estado == "PERSEGUINDO":
        tempo_recalculo_caminho -= dt
        if tempo_recalculo_caminho <= 0:
            tempo_recalculo_caminho = TEMPO_RECALCULO
            novo = bfs_caminho(GRAFO_LABIRINTO, celula_inimigo, ultima_celula_jogador)
            caminho_inimigo = novo if novo is not None else []
        velocidade = VELOCIDADE_INIMIGO_PERSEGUE
    else:
        if not caminho_inimigo:
            # escolhe um ponto qualquer do labirinto e vai ate la pelo BFS
            destino = random.choice(CELULAS_LIVRES)
            novo = bfs_caminho(GRAFO_LABIRINTO, celula_inimigo, destino)
            caminho_inimigo = novo if novo is not None else []
        velocidade = VELOCIDADE_INIMIGO_PATRULHA

    mover_inimigo_pelo_caminho(dt, velocidade)


def mover_inimigo_pelo_caminho(dt, velocidade):
    """Anda em direcao ao centro da proxima celula do caminho do BFS."""
    if not caminho_inimigo:
        return

    alvo_x, alvo_y = celula_para_pos(*caminho_inimigo[0])
    dx = alvo_x - inimigo.x
    dy = alvo_y - inimigo.y
    dist = math.hypot(dx, dy)

    if dist < 4:
        caminho_inimigo.pop(0)  # chegou nessa celula, vai pra proxima
        return

    dx /= dist
    dy /= dist
    inimigo.x, inimigo.y = mover_com_colisao(
        inimigo.x, inimigo.y, dx * velocidade * dt, dy * velocidade * dt, RAIO_INIMIGO)


def calcular_direcao():
    dx = 0
    dy = 0
    if keyboard.left or keyboard.a:
        dx -= 1
    if keyboard.right or keyboard.d:
        dx += 1
    if keyboard.up or keyboard.w:
        dy -= 1
    if keyboard.down or keyboard.s:
        dy += 1
    return dx, dy


def animar_personagem(dx, dy):
    if abs(dx) > abs(dy):
        if dx > 0:
            miranha.image = "sprite7" if miranha.image != "sprite7" else "sprite8"
        else:
            miranha.image = "sprite5" if miranha.image != "sprite5" else "sprite6"
    else:
        if dy > 0:
            miranha.image = "sprite3" if miranha.image != "sprite3" else "sprite4"
        else:
            miranha.image = "sprite1" if miranha.image != "sprite1" else "sprite2"
    redimensionar(miranha, TAMANHO_PERSONAGEM)


def desenhar_menu():
    screen.draw.text("LABIRINTO - MIRANHA", center=(WIDTH // 2, HEIGHT // 2 - 140),
                     fontsize=54, color="black")

    linhas = [
        "Setas ou WASD: mover",
        "Q: dash",
        "P: pausar / continuar",
        f"Colete {PONTOS_PARA_VENCER} moedas fugindo do inimigo!",
    ]
    y = HEIGHT // 2 - 40
    for linha in linhas:
        screen.draw.text(linha, center=(WIDTH // 2, y), fontsize=26, color=(60, 60, 60))
        y += 34

    screen.draw.text("Pressione ESPACO para comecar", center=(WIDTH // 2, HEIGHT // 2 + 160),
                     fontsize=32, color=(0, 130, 0))


def desenhar_overlay_pausa():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.surface.blit(overlay, (0, 0))

    screen.draw.text("PAUSADO", center=(WIDTH // 2, HEIGHT // 2 - 20), fontsize=60, color="white")
    screen.draw.text("Pressione P para continuar", center=(WIDTH // 2, HEIGHT // 2 + 40),
                     fontsize=26, color="white")


def draw():
    screen.fill((255, 255, 255))

    if estado_jogo == "MENU":
        desenhar_menu()
        return

    screen.blit(labirinto_img, (OFF_X, OFF_Y))

    if estado_jogo in ("JOGANDO", "PAUSADO"):
        coin.draw()
        inimigo.draw()
        miranha.draw()

        # "!" vermelho em cima do inimigo quando ele esta te perseguindo
        if ia_estado == "PERSEGUINDO":
            screen.draw.text("!", center=(inimigo.x, inimigo.y - 16), fontsize=26, color="red")

        screen.draw.text(f"Pontos: {pontos} / {PONTOS_PARA_VENCER}", (22, 22), fontsize=28, color="white")
        screen.draw.text(f"Vidas: {vidas}", (WIDTH - 130, 22), fontsize=28, color="red")

        if dash_cooldown_restante > 0:
            screen.draw.text(
                f"Dash recarregando... {dash_cooldown_restante:.1f}s",
                (22, HEIGHT - 36), fontsize=20, color=(200, 200, 200))
        else:
            screen.draw.text("Dash pronto (Q)", (22, HEIGHT - 36), fontsize=20, color=(80, 255, 80))

    if estado_jogo == "PAUSADO":
        desenhar_overlay_pausa()

    elif estado_jogo == "GAMEOVER":
        screen.draw.text("GAME OVER", center=(WIDTH // 2, HEIGHT // 2 - 30), fontsize=70, color="red")
        screen.draw.text("Pressione ESPACO para reiniciar", center=(WIDTH // 2, HEIGHT // 2 + 40), fontsize=26, color="black")

    elif estado_jogo == "VITORIA":
        screen.draw.text("VOCE VENCEU!", center=(WIDTH // 2, HEIGHT // 2 - 30), fontsize=60, color=(0, 130, 0))
        screen.draw.text(f"Pontuacao Final: {pontos}", center=(WIDTH // 2, HEIGHT // 2 + 30), fontsize=32, color="black")
        screen.draw.text("Pressione ESPACO para jogar novamente", center=(WIDTH // 2, HEIGHT // 2 + 80), fontsize=24, color="black")


def update(dt):
    global pontos, vidas, estado_jogo, anim_timer
    global dash_ativo, dash_tempo_restante, dash_cooldown_restante, dash_dir_x, dash_dir_y
    global direcao_atual_x, direcao_atual_y

    if estado_jogo == "MENU":
        if keyboard.space:
            reiniciar_jogo_completo()
        return

    if estado_jogo == "PAUSADO":
        return

    if estado_jogo in ("GAMEOVER", "VITORIA"):
        if keyboard.space:
            reiniciar_jogo_completo()
        return

    # ---------------- estado_jogo == "JOGANDO" ----------------

    dx, dy = calcular_direcao()
    esta_movendo = dx != 0 or dy != 0

    if esta_movendo:
        comprimento = math.hypot(dx, dy)
        dx = dx / comprimento
        dy = dy / comprimento
        direcao_atual_x, direcao_atual_y = dx, dy

    if dash_cooldown_restante > 0:
        dash_cooldown_restante -= dt
        if dash_cooldown_restante < 0:
            dash_cooldown_restante = 0

    if dash_ativo:
        dash_tempo_restante -= dt
        if dash_tempo_restante <= 0:
            dash_ativo = False

    if dash_ativo:
        vel_x = dash_dir_x * VELOCIDADE_DASH * dt
        vel_y = dash_dir_y * VELOCIDADE_DASH * dt
    elif esta_movendo:
        vel_x = dx * VELOCIDADE_JOGADOR * dt
        vel_y = dy * VELOCIDADE_JOGADOR * dt
    else:
        vel_x = 0
        vel_y = 0

    if vel_x != 0 or vel_y != 0:
        miranha.x, miranha.y = mover_com_colisao(miranha.x, miranha.y, vel_x, vel_y, RAIO_JOGADOR)

        anim_timer += dt
        if anim_timer >= ANIM_COOLDOWN:
            animar_personagem(vel_x, vel_y)
            anim_timer = 0

    if miranha.colliderect(coin):
        pontos += 1
        coin.x, coin.y = posicao_livre_aleatoria(RAIO_COIN, pos_evitar=(miranha.x, miranha.y), dist_minima=80)
        if pontos >= PONTOS_PARA_VENCER:
            estado_jogo = "VITORIA"

    # ---------- inimigo: percebe -> persegue (BFS) / patrulha ----------
    atualizar_ia_inimigo(dt)

    if miranha.colliderect(inimigo):
        vidas -= 1
        if vidas <= 0:
            estado_jogo = "GAMEOVER"
        else:
            resetar_posicoes()


def on_key_down(key):
    global dash_ativo, dash_tempo_restante, dash_cooldown_restante, dash_dir_x, dash_dir_y
    global estado_jogo

    if key == keys.Q and estado_jogo == "JOGANDO":
        if dash_cooldown_restante <= 0 and not dash_ativo:
            dash_ativo = True
            dash_tempo_restante = DASH_DURACAO
            dash_cooldown_restante = DASH_COOLDOWN
            dash_dir_x = direcao_atual_x
            dash_dir_y = direcao_atual_y

    if key == keys.P:
        if estado_jogo == "JOGANDO":
            estado_jogo = "PAUSADO"
        elif estado_jogo == "PAUSADO":
            estado_jogo = "JOGANDO"


pgzrun.go()