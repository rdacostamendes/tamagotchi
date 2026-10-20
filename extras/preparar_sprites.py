"""
Recorta as spritesheets (6 frames cada) em PNGs individuais com fundo transparente.

Uso:  python preparar_sprites.py <pasta_das_imagens> <pasta_de_saida>
(precisa de: pip install pillow numpy scipy)

Para cada estágio gera:  <estagio>_1.png ... <estagio>_6.png
Todos os frames de um estágio ficam do MESMO tamanho, alinhados pelos pés,
para o bichinho não "pular" de posição ao trocar de frame.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

# nome do estágio -> arquivo da spritesheet
SHEETS = {
    "bebe": "bebe.jfif",
    "crianca": "crianca.jfif",
    "adolescente": "adolecente.jpg",
    "adulto": "Adulto.jfif",
    "ancestral": "Ancestral.jfif",
}

# Altura (em "pixels de arte") do frame mais alto de cada estágio.
# O jogo amplia tudo com ESCALA_PIXEL (inteiro), então o pixel fica quadradão
# e nítido, como num Tamagotchi de verdade. Mude aqui para mudar o tamanho.
ALTURA_ARTE = {
    "bebe": 56,
    "crianca": 66,
    "adolescente": 74,
    "adulto": 88,
    "ancestral": 96,
}
ALTURA_OVO = 52


def achar_celulas(mascara):
    """Divide a folha em 6 células (3 colunas x 2 linhas) pelos vãos vazios."""
    h, w = mascara.shape
    # Colunas: procura os 2 maiores vãos verticais vazios perto de w/3 e 2w/3
    perfil_x = mascara.sum(axis=0)
    cortes_x = []
    for alvo in (w // 3, 2 * w // 3):
        faixa = range(int(alvo - w * 0.08), int(alvo + w * 0.08))
        cortes_x.append(min(faixa, key=lambda x: perfil_x[x]))
    # Linha: procura o vão horizontal perto de h/2
    perfil_y = mascara.sum(axis=1)
    faixa = range(int(h * 0.42), int(h * 0.58))
    corte_y = min(faixa, key=lambda y: perfil_y[y])
    xs = [0] + cortes_x + [w]
    ys = [0, corte_y, h]
    celulas = []
    for r in range(2):
        for c in range(3):
            celulas.append((xs[c], ys[r], xs[c + 1], ys[r + 1]))
    return celulas


def extrair_frame(rgb, caixa):
    """Devolve o dragão (RGBA, recortado) de uma célula, sem fundo e sem texto."""
    x0, y0, x1, y1 = caixa
    cel = rgb[y0:y1, x0:x1].astype(np.int16)

    # "Não é fundo" = pixel que se afasta do branco/off-white
    dist_branco = 255 - cel.min(axis=2)
    nao_fundo = dist_branco > 28

    # Junta pixels próximos (fecha furinhos de 1-2 px) e acha as manchas
    fechado = ndimage.binary_closing(nao_fundo, iterations=2)
    rotulos, n = ndimage.label(fechado)
    if n == 0:
        raise RuntimeError("célula vazia")
    areas = ndimage.sum(fechado, rotulos, range(1, n + 1))
    maior = int(np.argmax(areas)) + 1
    corpo = rotulos == maior

    # Preenche buracos internos (ex.: vão entre asa e cauda NÃO deve ser preenchido,
    # então só usamos a mancha como máscara de "o que é do dragão")
    corpo_dilatado = ndimage.binary_dilation(corpo, iterations=2)
    alfa = nao_fundo & corpo_dilatado

    # Suaviza fiapos: remove pontinhos soltos
    rot2, n2 = ndimage.label(alfa)
    if n2 > 1:
        areas2 = ndimage.sum(alfa, rot2, range(1, n2 + 1))
        manter = [i + 1 for i, a in enumerate(areas2) if a >= areas2.max() * 0.02]
        alfa = np.isin(rot2, manter)

    rgba = np.zeros((cel.shape[0], cel.shape[1], 4), dtype=np.uint8)
    rgba[..., :3] = cel.astype(np.uint8)
    rgba[..., 3] = (alfa * 255).astype(np.uint8)

    ys, xs = np.where(alfa)
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def reduzir(im, escala):
    """Reduz fazendo média de cor (BOX) sem 'sangrar' branco nas bordas
    e deixa a transparência 100% ligada ou desligada (borda nítida)."""
    novo = (max(1, round(im.width * escala)), max(1, round(im.height * escala)))
    pre = im.convert("RGBa").resize(novo, Image.BOX).convert("RGBA")
    a = np.array(pre)
    a[..., 3] = np.where(a[..., 3] >= 110, 255, 0)
    return Image.fromarray(a, "RGBA")


def preparar_ovo(pasta_in, pasta_out):
    im = Image.open(os.path.join(pasta_in, "1_Ovo.png")).convert("RGBA")
    a = np.array(im)
    # o PNG do ovo já tem fundo transparente; remove só sombras muito fracas
    a[..., 3] = np.where(a[..., 3] >= 40, a[..., 3], 0)
    im = Image.fromarray(a, "RGBA")
    im = im.crop(im.getbbox())
    reduzir(im, ALTURA_OVO / im.height).save(os.path.join(pasta_out, "ovo.png"))
    print("ovo: ok")


def processar(pasta_in, pasta_out):
    os.makedirs(pasta_out, exist_ok=True)
    for estagio, arquivo in SHEETS.items():
        caminho = os.path.join(pasta_in, arquivo)
        rgb = np.array(Image.open(caminho).convert("RGB"))
        mascara = (255 - rgb.min(axis=2)) > 28
        frames = [extrair_frame(rgb, c) for c in achar_celulas(mascara)]

        # Escala única para o estágio: o frame mais alto vira ALTURA_SAIDA
        maior_h = max(f.shape[0] for f in frames)
        escala = ALTURA_ARTE[estagio] / maior_h
        redim = [reduzir(Image.fromarray(f, "RGBA"), escala) for f in frames]

        # Tela comum do estágio, alinhando pelos pés (base) e centro horizontal
        L = max(i.width for i in redim) + 2
        A = max(i.height for i in redim) + 1
        for n, im in enumerate(redim, start=1):
            tela = Image.new("RGBA", (L, A), (0, 0, 0, 0))
            tela.paste(im, ((L - im.width) // 2, A - im.height), im)
            tela.save(os.path.join(pasta_out, f"{estagio}_{n}.png"))
        print(f"{estagio}: 6 frames de {L}x{A}px")


if __name__ == "__main__":
    processar(sys.argv[1], sys.argv[2])
    preparar_ovo(sys.argv[1], sys.argv[2])
