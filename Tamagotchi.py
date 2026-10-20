import datetime
import math
import os
import random
import sys
import pygame

pygame.init()

# Configurações de Tela
LARGURA, ALTURA = 480, 640
tela = pygame.display.set_mode((LARGURA, ALTURA))
pygame.display.set_caption("Tamagotchi 1.3 - RCM")
relogio = pygame.time.Clock()

# Cores
BRANCO = (245, 245, 245)
PRETO = (20, 20, 20)
VERDE = (46, 204, 113)
AZUL = (52, 152, 219)
AZUL_CLARO = (135, 206, 250)
AMARELO = (241, 196, 15)
VERMELHO = (231, 76, 60)
MARROM = (139, 69, 19)
CINZA = (189, 195, 199)
CINZA_ESCURO = (100, 100, 100)
ROXO = (155, 89, 182)
VERDE_DARK = (39, 174, 96)
ROSA_CLARO = (255, 192, 203)
BEGE_OVO = (245, 235, 210)

# Fontes
fonte_p = pygame.font.SysFont("arial", 14)
fonte_m = pygame.font.SysFont("arial", 18, bold=True)
fonte_g = pygame.font.SysFont("arial", 26, bold=True)

# Overlay Escuro para Luz Apagada
overlay_escuridao = pygame.Surface((LARGURA, ALTURA))
overlay_escuridao.fill((10, 10, 30))
overlay_escuridao.set_alpha(220)

# ---------------------------------------------------------------------------
# SPRITES (PIXEL ART)
# ---------------------------------------------------------------------------
# As imagens ficam na pasta "assets", ao lado deste arquivo.
PASTA_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Cada pixel do desenho vira ESCALA_PIXEL x ESCALA_PIXEL pixels na tela.
# Quer o bichinho maior? Troque por 3 (sempre um número inteiro!).
ESCALA_PIXEL = 2

# Linha do "chão" onde o bichinho pisa (coordenada y na tela).
CHAO_Y = 365

# Estágios da vida: (nome do arquivo, nome na tela, dias de jogo até o próximo).
# 1 dia de jogo = 120 segundos reais. Mude os números para evoluir mais
# rápido ou mais devagar. "None" = fica nesse estágio para sempre.
ESTAGIOS = [
    ("bebe", "Bebê", 2),
    ("crianca", "Criança", 5),
    ("adolescente", "Adolescente", 10),
    ("adulto", "Adulto", 20),
    ("ancestral", "Ancestral", None),
]

# Qual frame (1 a 6) da spritesheet usar em cada situação.
FRAME_PARADO_A = 1  # olhando para frente
FRAME_PARADO_B = 2  # olhando para cima
FRAME_DORMINDO = 3  # olhos fechados
FRAME_COMENDO = 4  # feliz, boca aberta, pulinho
FRAME_MAL = 5  # abaixado e desanimado
FRAME_ANDAR_B = 6  # balançando a cauda (alterna com o frame 1 ao andar)

# Nestes estados o bichinho para de andar e fica abaixado (frame 5).
ESTADOS_RUINS = ("DOENTE", "COM FRIO", "COM CALOR", "NECESSITADO", "TRISTE")

# A cada quantos "ticks" (1 tick = 1/60 s) o desenho troca de frame.
TICKS_POR_FRAME = 15


def carregar_imagem(nome):
  caminho = os.path.join(PASTA_ASSETS, nome)
  try:
    img = pygame.image.load(caminho).convert_alpha()
  except (FileNotFoundError, pygame.error):
    print(f"Não encontrei a imagem: {caminho}")
    print("Confira se a pasta 'assets' está junto do Tamagotchi.py")
    pygame.quit()
    sys.exit()
  # scale (e não smoothscale) mantém os pixels bem nítidos
  larg, alt = img.get_size()
  return pygame.transform.scale(img, (larg * ESCALA_PIXEL, alt * ESCALA_PIXEL))


IMG_OVO = carregar_imagem("ovo.png")

# SPRITES["bebe"][1] ... SPRITES["bebe"][6], e assim por diante
SPRITES = {}
for _chave, _nome, _dias in ESTAGIOS:
  SPRITES[_chave] = {n: carregar_imagem(f"{_chave}_{n}.png") for n in range(1, 7)}

# Guarda as versões espelhadas/coloridas para não refazer a cada frame
_cache_sprites = {}


def obter_sprite(chave, frame, espelhado, tinta):
  """Devolve o sprite pronto: espelhado (se vai para a esquerda) e/ou tingido."""
  k = (chave, frame, espelhado, tinta)
  if k not in _cache_sprites:
    img = SPRITES[chave][frame]
    if espelhado:
      img = pygame.transform.flip(img, True, False)
    if tinta is not None:
      img = img.copy()
      img.fill(tinta, special_flags=pygame.BLEND_RGBA_MULT)
    _cache_sprites[k] = img
  return _cache_sprites[k]


def estagio_por_dias(dias):
  """Dado a idade em dias de jogo, devolve (arquivo, nome) do estágio."""
  for chave, nome, ate in ESTAGIOS:
    if ate is None or dias < ate:
      return chave, nome
  return ESTAGIOS[-1][0], ESTAGIOS[-1][1]


# === CENARIO ===============================================================
# CENÁRIO (dia / tarde / noite) + FOGUEIRA ANIMADA
# ---------------------------------------------------------------------------
# Área da tela onde o cenário aparece (entre o cabeçalho e os botões).
AREA_CENARIO = pygame.Rect(0, 120, LARGURA, 340)

# Imagens do cenário (na pasta "assets"). Use as versões SEM fogo aceso:
# a chama é desenhada pelo código, para poder tremular e apagar.
ARQUIVOS_CENARIO = {
    "dia": "cenario_dia.png",
    "tarde": "cenario_tarde.png",
    "noite": "cenario_noite.png",
}
NOMES_PERIODO = {"dia": "Dia", "tarde": "Tarde", "noite": "Noite"}

# Cor de reserva, caso alguma imagem não seja encontrada.
COR_RESERVA = {"dia": (110, 170, 220), "tarde": (200, 120, 90), "noite": (25, 25, 60)}

# Horários (hora cheia, 0 a 23): dia 6h-16h, tarde 16h-19h, noite 19h-6h.
HORA_INICIO_DIA = 6
HORA_INICIO_TARDE = 16
HORA_INICIO_NOITE = 19

# Quantos segundos dura a transição suave (fade) entre dois cenários.
SEGUNDOS_FADE = 2.0

# As imagens são largas (16:9) e a janela é "em pé". A imagem é ajustada à
# altura da área e cortada dos lados. Aumente este número para mostrar mais
# o lado direito da caverna, diminua para mostrar mais o lado esquerdo.
CENARIO_DESLOC_X = 80

# Onde fica a fogueira na imagem, em fração da imagem (0.0 a 1.0).
# Se a chama ficar fora do lugar, ajuste aqui. (X: 0=esquerda, 1=direita;
# Y: 0=topo, 1=base. Este Y é a base da chama, onde ficam as achas.)
FOGO_REL_X = 0.292
FOGO_REL_Y = 0.758


def periodo_por_hora(hora):
  """Devolve 'dia', 'tarde' ou 'noite' para uma hora (0 a 23)."""
  if HORA_INICIO_DIA <= hora < HORA_INICIO_TARDE:
    return "dia"
  if HORA_INICIO_TARDE <= hora < HORA_INICIO_NOITE:
    return "tarde"
  return "noite"


class Cenario:
  """Guarda os 3 fundos e faz o fade quando o período muda."""

  def __init__(self):
    self.imagens = {}
    self.pos_fogo = (AREA_CENARIO.x + 100, AREA_CENARIO.y + 260)
    # (largura, altura, deslocamento) da imagem ajustada; serve para achar
    # na tela qualquer ponto da imagem (fogueira, cristais...)
    self.geo = (609, AREA_CENARIO.height, CENARIO_DESLOC_X)
    for periodo, arquivo in ARQUIVOS_CENARIO.items():
      self.imagens[periodo] = self._carregar(periodo, arquivo)

    self.forcado = None  # None = automático (hora real); senão 'dia', etc.
    self.atual = self._periodo_desejado()
    self.anterior = None
    self.fade = 1.0  # 1.0 = transição terminada

  def _carregar(self, periodo, arquivo):
    caminho = os.path.join(PASTA_ASSETS, arquivo)
    try:
      img = pygame.image.load(caminho).convert()
    except (FileNotFoundError, pygame.error):
      print(f"Não encontrei o cenário: {caminho} (usando cor lisa)")
      surf = pygame.Surface(AREA_CENARIO.size)
      surf.fill(COR_RESERVA[periodo])
      return surf

    # Ajusta a imagem para cobrir a área inteira, mantendo a proporção
    larg, alt = img.get_size()
    escala = max(AREA_CENARIO.width / larg, AREA_CENARIO.height / alt)
    nova_larg = max(AREA_CENARIO.width, round(larg * escala))
    nova_alt = max(AREA_CENARIO.height, round(alt * escala))
    img = pygame.transform.smoothscale(img, (nova_larg, nova_alt))

    # Corta os lados (e o que sobrar embaixo) para caber na área
    desloc = min(CENARIO_DESLOC_X, nova_larg - AREA_CENARIO.width)
    recorte = img.subsurface(
        (desloc, 0, AREA_CENARIO.width, AREA_CENARIO.height)
    ).copy()

    # A posição da fogueira na tela, calculada com a mesma conta
    self.geo = (nova_larg, nova_alt, desloc)
    self.pos_fogo = self.pos_na_tela(FOGO_REL_X, FOGO_REL_Y)
    return recorte

  def pos_na_tela(self, rel_x, rel_y):
    """Converte um ponto da imagem (frações 0 a 1) em posição na tela."""
    larg, alt, desloc = self.geo
    return (
        AREA_CENARIO.x + int(rel_x * larg) - desloc,
        AREA_CENARIO.y + int(rel_y * alt),
    )

  def _periodo_desejado(self):
    if self.forcado:
      return self.forcado
    return periodo_por_hora(datetime.datetime.now().hour)

  def alternar_teste(self):
    """Tecla T: dia -> tarde -> noite -> volta para o automático."""
    ordem = [None, "dia", "tarde", "noite"]
    proximo = (ordem.index(self.forcado) + 1) % len(ordem)
    self.forcado = ordem[proximo]

  def atualizar(self):
    desejado = self._periodo_desejado()
    if desejado != self.atual:
      self.anterior = self.atual
      self.atual = desejado
      self.fade = 0.0
    if self.fade < 1.0:
      self.fade = min(1.0, self.fade + 1.0 / (60.0 * SEGUNDOS_FADE))

  def desenhar(self, tela):
    if self.fade < 1.0 and self.anterior:
      tela.blit(self.imagens[self.anterior], AREA_CENARIO.topleft)
      nova = self.imagens[self.atual]
      nova.set_alpha(int(255 * self.fade))
      tela.blit(nova, AREA_CENARIO.topleft)
      nova.set_alpha(255)
    else:
      tela.blit(self.imagens[self.atual], AREA_CENARIO.topleft)

    # Aviso discreto enquanto o modo teste (tecla T) está ligado
    if self.forcado:
      desenhar_texto_legivel(
          fonte_p,
          f"Teste: {NOMES_PERIODO[self.forcado]} (T muda)",
          BRANCO,
          (AREA_CENARIO.x + 8, AREA_CENARIO.y + 6),
      )


class Fogueira:
  """Chama desenhada por código, com tremulação, brilho e faíscas."""

  LARG = 14  # tamanho da chama em "pixels de arte"
  ALT = 24
  ESCALA = 2  # cada pixel de arte vira 2x2 na tela

  # Camadas de fora para dentro: (cor, largura relativa, altura máxima)
  CAMADAS = [
      ((200, 50, 20), 1.00, 1.00),
      ((245, 120, 25), 0.78, 0.85),
      ((255, 200, 60), 0.52, 0.65),
      ((255, 245, 200), 0.26, 0.42),
  ]

  def __init__(self, x, y):
    self.x = x  # centro da fogueira na tela
    self.y = y  # base da chama na tela
    self.forca = 1.0  # 1 = acesa, 0 = apagada (muda aos poucos)
    self.t = 0
    self.chama = pygame.Surface((self.LARG, self.ALT), pygame.SRCALPHA)
    self.chama_grande = pygame.Surface(
        (self.LARG * self.ESCALA, self.ALT * self.ESCALA), pygame.SRCALPHA
    )
    self.faiscas = []  # cada faísca: [x, y, vida]
    self.brilho = self._criar_brilho(70)
    self._redesenhar_chama()

  def _criar_brilho(self, raio):
    """Círculo de luz laranja, mais forte no meio e sumindo nas bordas."""
    surf = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
    for r in range(raio, 0, -1):
      alpha = int(70 * (1 - r / raio) ** 2)
      pygame.draw.circle(surf, (255, 150, 50, alpha), (raio, raio), r)
    return surf

  def _redesenhar_chama(self):
    self.chama.fill((0, 0, 0, 0))
    altura = int(self.ALT * self.forca * (0.80 + 0.20 * random.random()))
    centro = self.LARG / 2 - 0.5
    for i in range(altura):  # i = 0 é a base da chama
      p = i / max(1, altura)  # 0 = base, 1 = ponta
      meia = 6.0 * (0.55 + 0.45 * min(1.0, p * 4)) * (1 - p) ** 0.8
      # a ponta balança mais que a base
      balanco = math.sin(self.t * 0.12 + p * 4.0) * p * 2.4
      balanco += random.uniform(-0.5, 0.5) * p
      cx = centro + balanco
      y = self.ALT - 1 - i
      for cor, larg_rel, alt_max in self.CAMADAS:
        if p > alt_max:
          continue
        mw = meia * larg_rel
        if mw < 0.5:
          continue
        x0 = int(round(cx - mw))
        x1 = int(round(cx + mw))
        pygame.draw.line(self.chama, cor, (x0, y), (x1, y))
    self.chama_grande = pygame.transform.scale(
        self.chama, self.chama_grande.get_size()
    )

  def atualizar(self, acesa):
    alvo = 1.0 if acesa else 0.0
    if self.forca < alvo:
      self.forca = min(alvo, self.forca + 0.03)
    elif self.forca > alvo:
      self.forca = max(alvo, self.forca - 0.03)

    self.t += 1
    if self.forca > 0:
      if self.t % 4 == 0:  # troca de forma a cada 4 ticks (visual pixel art)
        self._redesenhar_chama()
      # faíscas subindo
      if self.forca > 0.5 and random.random() < 0.08:
        self.faiscas.append(
            [self.x + random.uniform(-6, 6), self.y - 20, random.randint(40, 75)]
        )
    for f in self.faiscas:
      f[1] -= 0.7
      f[0] += math.sin(self.t * 0.2 + f[1] * 0.1) * 0.4
      f[2] -= 1
    self.faiscas = [f for f in self.faiscas if f[2] > 0]

  def desenhar(self, tela):
    if self.forca <= 0 and not self.faiscas:
      return

    if self.forca > 0:
      # brilho pulsando ao redor da chama
      pulso = 0.80 + 0.20 * math.sin(self.t * 0.25) + random.uniform(-0.05, 0.05)
      self.brilho.set_alpha(int(255 * self.forca * max(0.0, min(1.0, pulso))))
      tela.blit(
          self.brilho,
          (self.x - self.brilho.get_width() // 2, self.y - 30 - 70),
      )
      tela.blit(
          self.chama_grande,
          (self.x - self.chama_grande.get_width() // 2,
           self.y - self.chama_grande.get_height()),
      )

    for fx, fy, vida in self.faiscas:
      cor = (255, 190, 70) if vida > 20 else (200, 90, 30)
      pygame.draw.rect(tela, cor, (int(fx), int(fy), 2, 2))


def desenhar_texto_legivel(fonte, texto, cor, pos):
  """Escreve um texto sobre uma plaquinha escura translúcida (lê bem no cenário)."""
  img = fonte.render(texto, True, cor)
  placa = pygame.Surface((img.get_width() + 10, img.get_height() + 4), pygame.SRCALPHA)
  pygame.draw.rect(placa, (0, 0, 0, 130), placa.get_rect(), border_radius=5)
  tela.blit(placa, (pos[0] - 5, pos[1] - 2))
  tela.blit(img, pos)


def desenhar_sombra(tela, cx, y, largura):
  """Sombra suave embaixo do bichinho/ovo."""
  sombra = pygame.Surface((largura, 12), pygame.SRCALPHA)
  pygame.draw.ellipse(sombra, (0, 0, 0, 80), sombra.get_rect())
  tela.blit(sombra, (cx - largura // 2, y))


# Desenho do cocô em pixel art. Cada letra é um pixel:
# o = contorno, b = marrom, l = brilho, d = sombra, . = vazio
COCO_MAPA = [
    ".....oo.....",
    "....obbo....",
    "...obbbbo...",
    "..obbllbbo..",
    "..obbbbbbdo.",
    ".obbllbbbbdo",
    "obbbbbbbbbdo",
    "obllbbbbbddo",
    "obbbbbbbdddo",
    ".oooooooooo.",
]
COCO_CORES = {
    "o": (50, 28, 12),
    "b": (139, 87, 42),
    "l": (181, 125, 72),
    "d": (100, 60, 28),
}
ESCALA_COCO = 2  # cada pixel do desenho vira 2x2 na tela


def _criar_sprite_coco():
  larg, alt = len(COCO_MAPA[0]), len(COCO_MAPA)
  pequeno = pygame.Surface((larg, alt), pygame.SRCALPHA)
  for y, linha in enumerate(COCO_MAPA):
    for x, letra in enumerate(linha):
      if letra in COCO_CORES:
        pequeno.set_at((x, y), COCO_CORES[letra])
  return pygame.transform.scale(pequeno, (larg * ESCALA_COCO, alt * ESCALA_COCO))


SPRITE_COCO = _criar_sprite_coco()


def desenhar_coco(tela, cx, base_y, t):
  """Desenha um cocô com a base em base_y e uma fumacinha de fedor sutil."""
  larg, alt = SPRITE_COCO.get_size()
  desenhar_sombra(tela, cx, base_y - 6, larg + 6)
  tela.blit(SPRITE_COCO, (cx - larg // 2, base_y - alt))

  # Fedor: 3 fiapos esverdeados que sobem ondulando e vão sumindo
  fedor = pygame.Surface((40, 40), pygame.SRCALPHA)
  for i in range(3):
    u = (t * 0.012 + i / 3) % 1.0  # 0 = saindo do cocô, 1 = sumiu
    for k in range(4):  # cada fiapo é um rastro de 4 pontinhos
      uk = u - k * 0.06
      if uk < 0:
        continue
      x = 20 + (i - 1) * 8 + math.sin(uk * 7 + i * 2) * 4
      y = 38 - uk * 34
      alpha = int(170 * (1 - uk) ** 1.2 * (1 - 0.15 * k))
      pygame.draw.rect(fedor, (170, 200, 70, alpha), (int(x), int(y), 2, 2))
  tela.blit(fedor, (cx - 20, base_y - alt - 34))


# Cristais da caverna que brilham de leve quando a luz está apagada.
# Cada um: (x, y, cor) com x e y em fração da imagem (0 a 1).
# Se algum brilho ficar fora do cristal, ajuste o x/y dele aqui.
COR_CRISTAL_AZUL = (90, 170, 255)
COR_CRISTAL_ROXO = (190, 110, 255)
COR_CRISTAL_CIANO = (80, 230, 230)
CRISTAIS = [
    (0.384, 0.350, COR_CRISTAL_AZUL),
    (0.491, 0.350, COR_CRISTAL_AZUL),
    (0.408, 0.490, COR_CRISTAL_ROXO),
    (0.330, 0.215, COR_CRISTAL_ROXO),
    (0.240, 0.360, COR_CRISTAL_CIANO),
    (0.190, 0.940, COR_CRISTAL_ROXO),
    (0.078, 0.876, COR_CRISTAL_AZUL),
    (0.017, 0.386, COR_CRISTAL_AZUL),
    (0.982, 0.473, COR_CRISTAL_ROXO),
]
RAIO_BRILHO_CRISTAL = 26  # tamanho do brilho em pixels
FORCA_BRILHO_CRISTAL = 80  # 0 a 255; quanto menor, mais discreto


class Cristais:
  """Brilho suave nos cristais, que aparece quando a luz é apagada."""

  def __init__(self, cenario):
    self.forca = 0.0  # 0 = sem brilho, 1 = brilho total
    self.t = 0
    self.halos = {}  # um halo pronto para cada cor
    self.itens = []  # (x na tela, y na tela, cor, fase da pulsação)
    for rel_x, rel_y, cor in CRISTAIS:
      x, y = cenario.pos_na_tela(rel_x, rel_y)
      self.itens.append((x, y, cor, random.uniform(0, 6.28)))
      if cor not in self.halos:
        self.halos[cor] = self._criar_halo(RAIO_BRILHO_CRISTAL, cor)

  def _criar_halo(self, raio, cor):
    surf = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
    for r in range(raio, 0, -1):
      alpha = int(FORCA_BRILHO_CRISTAL * (1 - r / raio) ** 2)
      pygame.draw.circle(surf, (*cor, alpha), (raio, raio), r)
    return surf

  def atualizar(self, luz_acesa):
    self.t += 1
    if luz_acesa:
      self.forca = max(0.0, self.forca - 0.15)  # some rápido ao acender
    else:
      self.forca = min(1.0, self.forca + 0.03)  # surge devagar ao apagar

  def desenhar(self, tela):
    if self.forca <= 0:
      return
    tela.set_clip(AREA_CENARIO)  # o brilho não vaza para fora do cenário
    for x, y, cor, fase in self.itens:
      pulso = 0.75 + 0.25 * math.sin(self.t * 0.05 + fase)
      halo = self.halos[cor]
      halo.set_alpha(int(255 * self.forca * pulso))
      tela.blit(halo, (x - halo.get_width() // 2, y - halo.get_height() // 2))
    tela.set_clip(None)


cenario = Cenario()
fogueira = Fogueira(*cenario.pos_fogo)
cristais = Cristais(cenario)

# Quanto o bichinho pode chegar perto da fogueira (pixels à direita do centro
# dela, contando a borda das pedras). Ele anda até aqui e volta.
DISTANCIA_FOGUEIRA = 40
# === FIM CENARIO ===========================================================


class TamagotchiCompleto:

  def __init__(self, nome="Pet"):
    self.nome = nome
    self.vitalidade = 100.0
    self.fome = 50.0
    self.sede = 50.0
    self.humor = 50.0
    self.energia = 50.0
    self.higiene = 50.0

    # Ar Condicionado e Temperatura Estabilizada
    self.ar_ligado = False
    self.temperatura = 25.0

    # Digestão e Cocô
    self.digestao = 0.0
    self.cocos = []

    # Estágio de Ovo / Nascimento
    self.estagio = "Ovo"
    self.choca_progresso = 0.0  # de 0 a 100
    self.eclodiu = False

    # Crescimento Post-Ovo
    self.idade_segundos = 0
    self.peso = 1.0
    self.estagio_chave = "bebe"
    self.largura_pet, self.altura_pet = SPRITES["bebe"][1].get_size()

    # Estados
    self.esta_doente = False
    self.esta_vivo = True
    self.motivo_morte = ""
    self.dormindo = False
    self.luz_acesa = True
    self.estado_atual = "CHOCO"
    self.mensagem_negacao = ""
    self.tempo_mensagem = 0
    self.tempo_alimentando = 0

    # Posição e Movimento
    self.pos_x = LARGURA // 2
    self.direcao = 1  # 1 = vai para a direita, -1 = vai para a esquerda
    self.velocidade_x = 0.8  # pixels por tick
    self.caminhando = True
    self.timer_acao = random.randint(120, 300)  # ticks até trocar de ação
    self.contador_anim = 0  # conta ticks para trocar os frames

    # Cooldowns
    self.ultimo_alimento = 0
    self.cooldown_alimento = 2500

  def escolher_frame(self):
    """Decide qual frame (1 a 6) da spritesheet mostrar agora."""
    if self.dormindo or not self.esta_vivo:
      return FRAME_DORMINDO
    if pygame.time.get_ticks() < self.tempo_alimentando:
      return FRAME_COMENDO
    if self.estado_atual in ESTADOS_RUINS:
      return FRAME_MAL
    if self.caminhando:
      # alterna entre dois frames a cada TICKS_POR_FRAME
      alterna = (self.contador_anim // TICKS_POR_FRAME) % 2
      return FRAME_ANDAR_B if alterna else FRAME_PARADO_A
    # parado: troca de pose mais devagar (olha para frente / para cima)
    alterna = (self.contador_anim // (TICKS_POR_FRAME * 3)) % 2
    return FRAME_PARADO_B if alterna else FRAME_PARADO_A

  def pode_comer(self):
    return (
        pygame.time.get_ticks() - self.ultimo_alimento
    ) >= self.cooldown_alimento

  def alternar_luz(self):
    if not self.esta_vivo or not self.eclodiu:
      return
    self.luz_acesa = not self.luz_acesa
    if not self.luz_acesa and not self.dormindo:
      self.dormindo = True
    elif self.luz_acesa and self.dormindo:
      self.dormindo = False

  def alternar_ar(self):
    if not self.esta_vivo:
      return
    self.ar_ligado = not self.ar_ligado

  def mostrar_negacao(self, msg):
    self.mensagem_negacao = msg
    self.tempo_mensagem = pygame.time.get_ticks() + 2000

  def alimentar(self, tipo):
    if (
        not self.esta_vivo
        or not self.eclodiu
        or self.esta_doente
        or self.dormindo
    ):
      return

    if self.fome >= 100.0:
      self.mostrar_negacao("Não quero! Estou cheio!")
      return

    if not self.pode_comer():
      self.mostrar_negacao("Aguarde um pouco...")
      return

    alimentos = {
        "frango": {"fome": 40, "dig": 40, "peso": 0.2},
        "carne": {"fome": 50, "dig": 50, "peso": 0.3},
        "maca": {"fome": 20, "dig": 15, "peso": 0.05},
        "cenoura": {"fome": 15, "dig": 10, "peso": 0.03},
    }

    if tipo in alimentos:
      data = alimentos[tipo]
      self.fome = min(100.0, self.fome + data["fome"])
      self.digestao += data["dig"]
      self.peso += data["peso"]
      self.tempo_alimentando = pygame.time.get_ticks() + 1500

    self.ultimo_alimento = pygame.time.get_ticks()

    if self.digestao >= 100.0:
      self.fazer_coco()
      self.digestao = 0.0

  def beber_agua(self):
    if (
        not self.esta_vivo
        or not self.eclodiu
        or self.esta_doente
        or self.dormindo
    ):
      return
    if self.sede >= 100.0:
      self.mostrar_negacao("Sem sede agora!")
      return
    self.sede = min(100.0, self.sede + 40)

  def dar_remedio(self):
    if not self.esta_vivo or not self.eclodiu or self.dormindo:
      return
    if self.esta_doente:
      self.esta_doente = False
      self.humor = max(0.0, self.humor - 10)

  def fazer_coco(self):
    # Fica no chão, na altura dos pés do bichinho (com uma variaçãozinha),
    # e longe da fogueira
    cx = random.randint(max(140, int(fogueira.x) + 55), 420)
    cy = CHAO_Y + random.randint(-6, 8)  # cy = onde fica a base do cocô
    self.cocos.append((cx, cy))

  def limpar_ambiente(self):
    if not self.esta_vivo or not self.eclodiu or self.dormindo:
      return
    self.cocos.clear()

  def dar_banho(self):
    if not self.esta_vivo or not self.eclodiu or self.dormindo:
      return
    self.higiene = 100.0

  def atualizar(self):
    # Temperatura suave e realista
    if self.ar_ligado:
      if self.temperatura > 22.0:
        self.temperatura -= 0.002
      else:
        self.temperatura = max(18.0, self.temperatura - 0.0005)
    else:
      if self.temperatura < 25.0:
        self.temperatura += 0.002
      else:
        self.temperatura = min(38.0, self.temperatura + 0.0008)

    # Estágio de Ovo
    if not self.eclodiu:
      self.choca_progresso += 0.12
      if self.choca_progresso >= 100.0:
        self.eclodiu = True
        self.estagio = "Bebê"
        self.estado_atual = "FELIZ"
      return

    if not self.esta_vivo:
      return

    # Idade & Crescimento
    self.idade_segundos += 1 / 60.0
    self.contador_anim += 1
    dias_jogo = int(self.idade_segundos // 120)

    self.estagio_chave, self.estagio = estagio_por_dias(dias_jogo)
    self.largura_pet, self.altura_pet = SPRITES[self.estagio_chave][1].get_size()

    taxa = 0.003

    # Movimento: anda de um lado ao outro da tela, com pausas no meio
    ruim = self.estado_atual in ESTADOS_RUINS
    if not self.dormindo and not ruim:
      self.timer_acao -= 1
      if self.timer_acao <= 0:
        self.caminhando = not self.caminhando
        if self.caminhando:
          self.timer_acao = random.randint(180, 420)
          if random.random() < 0.35:  # às vezes sai andando para o outro lado
            self.direcao *= -1
        else:
          self.timer_acao = random.randint(90, 180)

      if self.caminhando:
        self.pos_x += self.direcao * self.velocidade_x

    # Nunca deixa o bichinho passar das bordas da tela
    # (e nunca passa por cima da fogueira: ela fica à esquerda dele)
    metade = self.largura_pet / 2
    limite_esq = max(metade + 8, fogueira.x + DISTANCIA_FOGUEIRA + metade)
    limite_dir = LARGURA - metade - 8
    if self.pos_x >= limite_dir:
      self.pos_x = limite_dir
      self.direcao = -1
    elif self.pos_x <= limite_esq:
      self.pos_x = limite_esq
      self.direcao = 1

    # Sono & Energia
    if self.dormindo:
      self.energia = min(100.0, self.energia + taxa * 2.0)
      if self.energia >= 100.0:
        self.dormindo = False
    else:
      self.energia = max(0.0, self.energia - taxa * 0.5)
      if not self.luz_acesa:
        self.humor = max(0.0, self.humor - taxa * 0.4)

    # Consumos
    multiplicador_sede = 1.5 if self.temperatura > 28.0 else 1.0
    self.sede = max(0.0, self.sede - taxa * 1.2 * multiplicador_sede)
    self.fome = max(0.0, self.fome - taxa * 1.0)
    self.humor = max(0.0, self.humor - taxa * 0.6)

    penalidade_coco = len(self.cocos) * 0.01
    self.higiene = max(0.0, self.higiene - (taxa * 0.5 + penalidade_coco))

    # Doenças
    if not self.esta_doente:
      if self.higiene < 25 or self.fome < 15 or self.temperatura < 21.0:
        if random.random() < 0.0001:
          self.esta_doente = True

    # Vitalidade
    dano_vitalidade = 0.0
    motivo_temp = ""
    if self.fome <= 0:
      dano_vitalidade += 0.01
      motivo_temp = "Fome Extrema"
    if self.sede <= 0:
      dano_vitalidade += 0.015
      motivo_temp = "Desidratação"
    if self.esta_doente:
      dano_vitalidade += 0.01
      motivo_temp = "Infecção sem Remédio"
    if self.temperatura < 20.0 or self.temperatura > 33.0:
      dano_vitalidade += 0.008
      motivo_temp = "Temperatura Extrema"

    if dano_vitalidade > 0:
      self.vitalidade = max(0.0, self.vitalidade - dano_vitalidade)
      if self.vitalidade <= 0:
        self.motivo_morte = motivo_temp
    else:
      if self.fome > 50 and self.sede > 50 and not self.esta_doente:
        self.vitalidade = min(100.0, self.vitalidade + 0.005)

    # Checagem de Morte
    if self.vitalidade <= 0:
      self.esta_vivo = False
      self.estado_atual = "MORTO"
      if not self.motivo_morte:
        self.motivo_morte = "Causas Naturais"
    elif self.dormindo:
      self.estado_atual = "DORMINDO"
    elif self.esta_doente:
      self.estado_atual = "DOENTE"
    elif self.temperatura < 21.0:
      self.estado_atual = "COM FRIO"
    elif self.temperatura > 28.0:
      self.estado_atual = "COM CALOR"
    elif self.fome < 30 or self.sede < 30:
      self.estado_atual = "NECESSITADO"
    elif self.humor < 30:
      self.estado_atual = "TRISTE"
    else:
      self.estado_atual = "FELIZ"


def desenhar_barra(tela, x, y, largura, altura, valor, cor, rotulo):
  txt = fonte_p.render(f"{rotulo}: {int(valor)}%", True, PRETO)
  tela.blit(txt, (x, y - 16))
  pygame.draw.rect(tela, CINZA, (x, y, largura, altura), border_radius=4)
  largura_p = int((valor / 100) * largura)
  if largura_p > 0:
    pygame.draw.rect(tela, cor, (x, y, largura_p, altura), border_radius=4)
  pygame.draw.rect(tela, PRETO, (x, y, largura, altura), 2, border_radius=4)


def desenhar_ovo(tela, cx, chao_y, pet, frame_animacao):
  progresso = pet.choca_progresso

  # O ovo só balança no lugar, de vez em quando. Quanto mais perto de
  # chocar, mais forte e mais seguido ele balança.
  ciclo = int(100 - progresso * 0.6)  # de 100 ticks (calmo) até 40 (agitado)
  t = frame_animacao % ciclo
  duracao = 36
  angulo = 0.0
  if t < duracao:
    forca = 6 + progresso * 0.08  # em graus
    angulo = math.sin(t / duracao * 4 * math.pi) * forca

  altura = IMG_OVO.get_height()
  # Gira o ovo "em pé" no chão (o pivô é a base dele)
  rad = math.radians(angulo)
  centro_x = cx - (altura / 2) * math.sin(rad)
  centro_y = chao_y - (altura / 2) * math.cos(rad)
  img = pygame.transform.rotate(IMG_OVO, angulo) if angulo else IMG_OVO
  ret = img.get_rect(center=(int(centro_x), int(centro_y)))

  # sombra no chão
  desenhar_sombra(tela, cx, chao_y - 6, 100)
  tela.blit(img, ret)

  msg_ovo = "O ovo está chocando..."
  larg_ovo = fonte_m.size(msg_ovo)[0]
  desenhar_texto_legivel(
      fonte_m,
      msg_ovo,
      BRANCO,
      (LARGURA // 2 - larg_ovo // 2, chao_y - altura - 36),
  )


def desenhar_lapide(tela, pet, btn_reiniciar):
  # Fundo Sombrio
  sombra = pygame.Surface((LARGURA, ALTURA))
  sombra.fill((0, 0, 0))
  sombra.set_alpha(180)
  tela.blit(sombra, (0, 0))

  # Lápide central
  lx, ly, lw, lh = LARGURA // 2 - 120, 160, 240, 260
  pygame.draw.rect(
      tela, CINZA_ESCURO, (lx, ly + 30, lw, lh - 30), border_radius=15
  )
  pygame.draw.circle(tela, CINZA_ESCURO, (lx + lw // 2, ly + 35), lw // 2)
  pygame.draw.rect(tela, PRETO, (lx, ly + 30, lw, lh - 30), 3, border_radius=15)
  pygame.draw.circle(
      tela, PRETO, (lx + lw // 2, ly + 35), lw // 2, 3
  )

  # Detalhes Cruz
  pygame.draw.rect(tela, CINZA, (lx + lw // 2 - 6, ly + 25, 12, 40))
  pygame.draw.rect(tela, CINZA, (lx + lw // 2 - 20, ly + 35, 40, 12))

  # Textos R.I.P
  txt_rip = fonte_g.render("R. I. P.", True, BRANCO)
  tela.blit(txt_rip, (LARGURA // 2 - txt_rip.get_width() // 2, ly + 80))

  txt_nome = fonte_m.render(f"Nome: {pet.nome}", True, BRANCO)
  tela.blit(txt_nome, (LARGURA // 2 - txt_nome.get_width() // 2, ly + 125))

  dias_vividos = int(pet.idade_segundos // 120)
  txt_idade = fonte_p.render(f"Viveu: {dias_vividos} dias", True, BRANCO)
  tela.blit(txt_idade, (LARGURA // 2 - txt_idade.get_width() // 2, ly + 155))

  txt_morte_label = fonte_p.render("Causa do falecimento:", True, ROSA_CLARO)
  tela.blit(
      txt_morte_label,
      (LARGURA // 2 - txt_morte_label.get_width() // 2, ly + 185),
  )

  txt_causa = fonte_p.render(f"{pet.motivo_morte}", True, VERMELHO)
  tela.blit(txt_causa, (LARGURA // 2 - txt_causa.get_width() // 2, ly + 205))

  # Botão Reiniciar
  pygame.draw.rect(tela, VERDE, btn_reiniciar, border_radius=8)
  pygame.draw.rect(tela, PRETO, btn_reiniciar, 2, border_radius=8)
  lbl_rei = fonte_m.render("REINICIAR PET", True, PRETO)
  tela.blit(
      lbl_rei,
      (
          btn_reiniciar.x
          + btn_reiniciar.width // 2
          - lbl_rei.get_width() // 2,
          btn_reiniciar.y + 10,
      ),
  )


def desenhar_pet(tela, pet, frame_animacao):
  frame = pet.escolher_frame()
  # Os desenhos originais olham para a direita; ao ir para a esquerda, espelha
  espelhado = pet.direcao == -1

  tinta = None  # cor que "multiplica" o desenho
  if not pet.esta_vivo:
    tinta = (110, 110, 120, 255)  # cinza
  elif pet.esta_doente:
    tinta = (190, 255, 190, 255)  # esverdeado
  img = obter_sprite(pet.estagio_chave, frame, espelhado, tinta)

  # Pulinho de 1 pixel de arte a cada passo (frame 6), dá jeito de caminhada
  pulo = ESCALA_PIXEL if frame == FRAME_ANDAR_B else 0

  tremer = 0
  if pet.esta_vivo and (pet.temperatura < 21.0 or pet.esta_doente):
    tremer = random.randint(-2, 2)

  x = int(pet.pos_x) - img.get_width() // 2 + tremer
  y = CHAO_Y - img.get_height() - pulo

  # sombra no chão
  larg_sombra = int(img.get_width() * 0.6)
  desenhar_sombra(tela, int(pet.pos_x), CHAO_Y - 6, larg_sombra)
  tela.blit(img, (x, y))

  if pet.dormindo and pet.esta_vivo:
    zx = x - 10 if espelhado else x + img.get_width() - 60
    desenhar_texto_legivel(fonte_g, "Z z z...", BRANCO, (zx, y - 24))


def obter_nome_pet():
  nome = ""
  digitando = True
  while digitando:
    tela.fill(BRANCO)
    titulo = fonte_g.render("Digite o Nome do seu Pet:", True, PRETO)
    tela.blit(titulo, (LARGURA // 2 - titulo.get_width() // 2, 180))

    pygame.draw.rect(tela, CINZA, (80, 250, 320, 50), border_radius=8)
    pygame.draw.rect(tela, PRETO, (80, 250, 320, 50), 2, border_radius=8)

    txt_nome = fonte_g.render(nome + "_", True, PRETO)
    tela.blit(txt_nome, (100, 260))

    instrucao = fonte_p.render(
        "Pressione ENTER para confirmar", True, CINZA_ESCURO
    )
    tela.blit(instrucao, (LARGURA // 2 - instrucao.get_width() // 2, 320))

    pygame.display.flip()

    for evento in pygame.event.get():
      if evento.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
      elif evento.type == pygame.KEYDOWN:
        if evento.key == pygame.K_RETURN and len(nome.strip()) > 0:
          digitando = False
        elif evento.key == pygame.K_BACKSPACE:
          nome = nome[:-1]
        elif len(nome) < 12 and evento.unicode.isalnum():
          nome += evento.unicode

  return nome.strip()


# Mini-jogos com recurso "Jogar Novamente"
def jogar_ppt(pet):
  escolhas = ["Pedra", "Papel", "Tesoura"]
  rodando_ppt = True
  resultado = ""

  while rodando_ppt:
    tela.fill(BRANCO)
    titulo = fonte_g.render("Pedra, Papel ou Tesoura", True, PRETO)
    tela.blit(titulo, (LARGURA // 2 - titulo.get_width() // 2, 80))

    btn_pedra = pygame.Rect(60, 200, 100, 50)
    btn_papel = pygame.Rect(190, 200, 100, 50)
    btn_tesoura = pygame.Rect(320, 200, 100, 50)

    btn_jogar_de_novo = pygame.Rect(80, 400, 150, 40)
    btn_sair = pygame.Rect(250, 400, 150, 40)

    for b, t in [
        (btn_pedra, "Pedra"),
        (btn_papel, "Papel"),
        (btn_tesoura, "Tesoura"),
    ]:
      pygame.draw.rect(tela, AZUL_CLARO, b, border_radius=6)
      pygame.draw.rect(tela, PRETO, b, 2, border_radius=6)
      lbl = fonte_m.render(t, True, PRETO)
      tela.blit(lbl, (b.x + 15, b.y + 12))

    # Botão Jogar Novamente
    pygame.draw.rect(tela, VERDE, btn_jogar_de_novo, border_radius=6)
    pygame.draw.rect(tela, PRETO, btn_jogar_de_novo, 2, border_radius=6)
    lbl_j = fonte_p.render("Jogar Novamente", True, PRETO)
    tela.blit(lbl_j, (btn_jogar_de_novo.x + 15, btn_jogar_de_novo.y + 10))

    # Botão Voltar
    pygame.draw.rect(tela, VERMELHO, btn_sair, border_radius=6)
    pygame.draw.rect(tela, PRETO, btn_sair, 2, border_radius=6)
    lbl_s = fonte_p.render("Voltar ao Pet", True, BRANCO)
    tela.blit(lbl_s, (btn_sair.x + 35, btn_sair.y + 10))

    if resultado:
      txt_res = fonte_m.render(resultado, True, PRETO)
      tela.blit(txt_res, (LARGURA // 2 - txt_res.get_width() // 2, 300))

    pygame.display.flip()

    for ev in pygame.event.get():
      if ev.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
      elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
        pos = ev.pos
        user_choice = None
        if btn_pedra.collidepoint(pos):
          user_choice = "Pedra"
        elif btn_papel.collidepoint(pos):
          user_choice = "Papel"
        elif btn_tesoura.collidepoint(pos):
          user_choice = "Tesoura"
        elif btn_jogar_de_novo.collidepoint(pos):
          resultado = ""
        elif btn_sair.collidepoint(pos):
          rodando_ppt = False

        if user_choice:
          bot_choice = random.choice(escolhas)
          if user_choice == bot_choice:
            resultado = f"Empate! Ambos escolheram {user_choice}"
            pet.humor = min(100.0, pet.humor + 5)
          elif (
              (user_choice == "Pedra" and bot_choice == "Tesoura")
              or (user_choice == "Papel" and bot_choice == "Pedra")
              or (user_choice == "Tesoura" and bot_choice == "Papel")
          ):
            resultado = f"Você Ganhou! {user_choice} vence {bot_choice}"
            pet.humor = min(100.0, pet.humor + 20)
          else:
            resultado = f"Você Perdeu! {bot_choice} vence {user_choice}"
            pet.humor = max(0.0, pet.humor - 5)


def jogar_velha(pet):
  tabuleiro = [""] * 9
  turno_jogador = True
  vencedor = None
  rodando_v = True

  def checar_vitoria(tb):
    comb = [
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    ]
    for a, b, c in comb:
      if tb[a] == tb[b] == tb[c] and tb[a] != "":
        return tb[a]
    if "" not in tb:
      return "Empate"
    return None

  while rodando_v:
    tela.fill(BRANCO)
    titulo = fonte_g.render("Jogo da Velha", True, PRETO)
    tela.blit(titulo, (LARGURA // 2 - titulo.get_width() // 2, 40))

    botoes_grid = []
    for i in range(9):
      x = 140 + (i % 3) * 70
      y = 100 + (i // 3) * 70
      r = pygame.Rect(x, y, 60, 60)
      botoes_grid.append(r)
      pygame.draw.rect(tela, CINZA, r, border_radius=4)
      pygame.draw.rect(tela, PRETO, r, 2, border_radius=4)
      txt = fonte_g.render(tabuleiro[i], True, PRETO)
      tela.blit(txt, (x + 20, y + 10))

    btn_jogar_de_novo = pygame.Rect(80, 380, 150, 40)
    btn_sair = pygame.Rect(250, 380, 150, 40)

    pygame.draw.rect(tela, VERDE, btn_jogar_de_novo, border_radius=6)
    pygame.draw.rect(tela, PRETO, btn_jogar_de_novo, 2, border_radius=6)
    lbl_j = fonte_p.render("Jogar Novamente", True, PRETO)
    tela.blit(lbl_j, (btn_jogar_de_novo.x + 15, btn_jogar_de_novo.y + 10))

    pygame.draw.rect(tela, VERMELHO, btn_sair, border_radius=6)
    pygame.draw.rect(tela, PRETO, btn_sair, 2, border_radius=6)
    lbl_s = fonte_p.render("Voltar ao Pet", True, BRANCO)
    tela.blit(lbl_s, (btn_sair.x + 35, btn_sair.y + 10))

    if vencedor:
      msg = (
          "Empate!"
          if vencedor == "Empate"
          else f"Vencedor: {'Você' if vencedor == 'X' else 'Pet'}!"
      )
      txt_v = fonte_m.render(msg, True, PRETO)
      tela.blit(txt_v, (LARGURA // 2 - txt_v.get_width() // 2, 325))

    pygame.display.flip()

    if not turno_jogador and not vencedor:
      pygame.time.delay(300)
      vazios = [i for i, v in enumerate(tabuleiro) if v == ""]
      if vazios:
        idx = random.choice(vazios)
        tabuleiro[idx] = "O"
        vencedor = checar_vitoria(tabuleiro)
        if vencedor == "O":
          pet.humor = max(0.0, pet.humor - 10)
        elif vencedor == "Empate":
          pet.humor = min(100.0, pet.humor + 5)
        turno_jogador = True

    for ev in pygame.event.get():
      if ev.type == pygame.QUIT:
        pygame.quit()
        sys.exit()
      elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
        pos = ev.pos
        if btn_jogar_de_novo.collidepoint(pos):
          tabuleiro = [""] * 9
          turno_jogador = True
          vencedor = None
        elif btn_sair.collidepoint(pos):
          rodando_v = False
        if turno_jogador and not vencedor:
          for i, r in enumerate(botoes_grid):
            if r.collidepoint(pos) and tabuleiro[i] == "":
              tabuleiro[i] = "X"
              vencedor = checar_vitoria(tabuleiro)
              if vencedor == "X":
                pet.humor = min(100.0, pet.humor + 25)
              elif vencedor == "Empate":
                pet.humor = min(100.0, pet.humor + 5)
              else:
                turno_jogador = False


nome_escolhido = obter_nome_pet()
pet = TamagotchiCompleto(nome_escolhido)

# Botões Inferiores Principais
btn_comida_menu = pygame.Rect(15, 520, 80, 40)
btn_agua = pygame.Rect(105, 520, 80, 40)
btn_interagir = pygame.Rect(195, 520, 80, 40)
btn_higiene = pygame.Rect(285, 520, 80, 40)
btn_vet = pygame.Rect(375, 520, 80, 40)

btn_luz = pygame.Rect(15, 575, 215, 40)
btn_ar = pygame.Rect(240, 575, 215, 40)

# Botão Reiniciar em Morte
btn_reiniciar_morte = pygame.Rect(LARGURA // 2 - 90, 400, 180, 45)

# Submenus
menu_aberto = None

btn_frango = pygame.Rect(15, 470, 70, 35)
btn_carne = pygame.Rect(90, 470, 70, 35)
btn_maca = pygame.Rect(165, 470, 70, 35)
btn_cenoura = pygame.Rect(240, 470, 70, 35)

btn_ppt = pygame.Rect(195, 470, 90, 35)
btn_velha = pygame.Rect(290, 470, 90, 35)

btn_limpar_env = pygame.Rect(285, 470, 80, 35)
btn_banho = pygame.Rect(370, 470, 80, 35)

frame_animacao = 0
rodando = True

while rodando:
  tela.fill(BRANCO)
  frame_animacao += 1

  for evento in pygame.event.get():
    if evento.type == pygame.QUIT:
      rodando = False
    elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_t:
      cenario.alternar_teste()  # T: testa dia / tarde / noite / automático
    elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
      pos = evento.pos

      # Ação de Reiniciar quando o pet morrer
      if not pet.esta_vivo:
        if btn_reiniciar_morte.collidepoint(pos):
          novo_nome = obter_nome_pet()
          pet = TamagotchiCompleto(novo_nome)
          continue

      if pet.esta_vivo and pet.eclodiu:
        if menu_aberto == "COMIDA":
          if btn_frango.collidepoint(pos):
            pet.alimentar("frango")
            menu_aberto = None
            continue
          elif btn_carne.collidepoint(pos):
            pet.alimentar("carne")
            menu_aberto = None
            continue
          elif btn_maca.collidepoint(pos):
            pet.alimentar("maca")
            menu_aberto = None
            continue
          elif btn_cenoura.collidepoint(pos):
            pet.alimentar("cenoura")
            menu_aberto = None
            continue

        elif menu_aberto == "INTERAGIR":
          if btn_ppt.collidepoint(pos):
            jogar_ppt(pet)
            menu_aberto = None
            continue
          elif btn_velha.collidepoint(pos):
            jogar_velha(pet)
            menu_aberto = None
            continue

        elif menu_aberto == "HIGIENE":
          if btn_limpar_env.collidepoint(pos):
            pet.limpar_ambiente()
            menu_aberto = None
            continue
          elif btn_banho.collidepoint(pos):
            pet.dar_banho()
            menu_aberto = None
            continue

        if btn_luz.collidepoint(pos):
          pet.alternar_luz()
        elif btn_ar.collidepoint(pos):
          pet.alternar_ar()
        elif btn_comida_menu.collidepoint(pos):
          menu_aberto = "COMIDA" if menu_aberto != "COMIDA" else None
        elif btn_agua.collidepoint(pos):
          pet.beber_agua()
          menu_aberto = None
        elif btn_interagir.collidepoint(pos):
          menu_aberto = "INTERAGIR" if menu_aberto != "INTERAGIR" else None
        elif btn_higiene.collidepoint(pos):
          menu_aberto = "HIGIENE" if menu_aberto != "HIGIENE" else None
        elif btn_vet.collidepoint(pos):
          pet.dar_remedio()
          menu_aberto = None

  pet.atualizar()

  # --- DESENHO DAS BARRAS ---
  desenhar_barra(
      tela, 140, 25, 200, 16, pet.vitalidade, VERDE_DARK, "Vitalidade"
  )

  desenhar_barra(tela, 20, 65, 100, 10, pet.fome, VERDE, "Fome")
  desenhar_barra(tela, 130, 65, 100, 10, pet.sede, AZUL_CLARO, "Sede")
  desenhar_barra(tela, 240, 65, 100, 10, pet.humor, AMARELO, "Humor")
  desenhar_barra(tela, 350, 65, 100, 10, pet.energia, AZUL, "Energia")

  # Temperatura
  txt_temp = fonte_m.render(f"{pet.temperatura:.1f}°C", True, PRETO)
  tela.blit(txt_temp, (410, 20))

  # Informações
  dias_vida = int(pet.idade_segundos // 120)
  txt_info = fonte_p.render(
      f"Nome: {pet.nome} | Idade: {dias_vida}d | Fase: {pet.estagio} | Peso:"
      f" {pet.peso:.1f}kg",
      True,
      PRETO,
  )
  tela.blit(txt_info, (20, 95))
  pygame.draw.line(tela, CINZA, (20, 115), (460, 115), 2)

  # Cenário (muda sozinho conforme a hora real) e fogueira
  cenario.atualizar()
  cenario.desenhar(tela)
  fogueira.atualizar(pet.luz_acesa)
  fogueira.desenhar(tela)

  # Cocôs
  for cx, cy in pet.cocos:
    desenhar_coco(tela, cx, cy, frame_animacao)

  # Desenho do Ovo ou do bichinho
  if not pet.eclodiu:
    desenhar_ovo(tela, LARGURA // 2, CHAO_Y, pet, frame_animacao)
  else:
    desenhar_pet(tela, pet, frame_animacao)

  # Balão de Negação
  if pygame.time.get_ticks() < pet.tempo_mensagem:
    larg_neg = fonte_p.size(pet.mensagem_negacao)[0]
    neg_x = max(10, min(LARGURA - larg_neg - 10, int(pet.pos_x) - 60))
    desenhar_texto_legivel(
        fonte_p, pet.mensagem_negacao, (255, 120, 110),
        (neg_x, CHAO_Y - pet.altura_pet - 30),
    )

  # Estado
  desenhar_texto_legivel(
      fonte_m, f"Estado: {pet.estado_atual}", BRANCO, (140, 420)
  )

  # Overlay para Luz Apagada
  if not pet.luz_acesa:
    tela.blit(overlay_escuridao, (0, 0))
  # Brilho dos cristais (desenhado depois do escuro, para não ser escurecido)
  cristais.atualizar(pet.luz_acesa)
  cristais.desenhar(tela)

  # --- RENDER DOS SUBMENUS ---
  if pet.esta_vivo and pet.eclodiu:
    if menu_aberto == "COMIDA":
      pygame.draw.rect(tela, CINZA, (10, 465, 310, 45), border_radius=6)
      for b, t in [
          (btn_frango, "Frango"),
          (btn_carne, "Carne"),
          (btn_maca, "Maçã"),
          (btn_cenoura, "Cenoura"),
      ]:
        pygame.draw.rect(tela, VERDE, b, border_radius=4)
        pygame.draw.rect(tela, PRETO, b, 1, border_radius=4)
        lbl = fonte_p.render(t, True, PRETO)
        tela.blit(lbl, (b.x + 8, b.y + 8))

    elif menu_aberto == "INTERAGIR":
      pygame.draw.rect(tela, CINZA, (190, 465, 200, 45), border_radius=6)
      for b, t in [(btn_ppt, "PPT"), (btn_velha, "J. Velha")]:
        pygame.draw.rect(tela, AMARELO, b, border_radius=4)
        pygame.draw.rect(tela, PRETO, b, 1, border_radius=4)
        lbl = fonte_p.render(t, True, PRETO)
        tela.blit(lbl, (b.x + 15, b.y + 8))

    elif menu_aberto == "HIGIENE":
      pygame.draw.rect(tela, CINZA, (280, 465, 180, 45), border_radius=6)
      for b, t in [(btn_limpar_env, "Limpar"), (btn_banho, "Banho")]:
        pygame.draw.rect(tela, MARROM, b, border_radius=4)
        pygame.draw.rect(tela, PRETO, b, 1, border_radius=4)
        lbl = fonte_p.render(t, True, BRANCO)
        tela.blit(lbl, (b.x + 12, b.y + 8))

  # --- BOTÕES PRINCIPAIS ---
  cor_comer = VERDE if pet.pode_comer() else CINZA_ESCURO
  botoes = [
      (btn_comida_menu, "Comer", cor_comer),
      (btn_agua, "Água", AZUL_CLARO),
      (btn_interagir, "Interagir", AMARELO),
      (btn_higiene, "Higiene", MARROM),
      (btn_vet, "VET", VERMELHO),
  ]

  for b, t, c in botoes:
    pygame.draw.rect(tela, c, b, border_radius=6)
    pygame.draw.rect(tela, PRETO, b, 2, border_radius=6)
    lbl = fonte_p.render(t, True, PRETO)
    tela.blit(lbl, (b.x + 8, b.y + 10))

  # Botão Luz
  txt_luz = "Luz: Apagada" if not pet.luz_acesa else "Luz: Acesa"
  pygame.draw.rect(
      tela, AMARELO if not pet.luz_acesa else ROXO, btn_luz, border_radius=6
  )
  pygame.draw.rect(tela, PRETO, btn_luz, 2, border_radius=6)
  lbl_luz = fonte_m.render(txt_luz, True, BRANCO if pet.luz_acesa else PRETO)
  tela.blit(
      lbl_luz,
      (
          btn_luz.x + btn_luz.width // 2 - lbl_luz.get_width() // 2,
          btn_luz.y + 8,
      ),
  )

  # Botão Ar Condicionado
  txt_ar = "Ar: LIGADO" if pet.ar_ligado else "Ar: DESLIGADO"
  cor_ar = AZUL_CLARO if pet.ar_ligado else CINZA
  pygame.draw.rect(tela, cor_ar, btn_ar, border_radius=6)
  pygame.draw.rect(tela, PRETO, btn_ar, 2, border_radius=6)
  lbl_ar = fonte_m.render(txt_ar, True, PRETO)
  tela.blit(
      lbl_ar,
      (btn_ar.x + btn_ar.width // 2 - lbl_ar.get_width() // 2, btn_ar.y + 8),
  )

  # Renderizar Tela de Lápide em caso de Morte
  if not pet.esta_vivo:
    desenhar_lapide(tela, pet, btn_reiniciar_morte)

  pygame.display.flip()
  relogio.tick(60)

pygame.quit()
sys.exit()