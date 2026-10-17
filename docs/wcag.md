# Acessibilidade — checklist WCAG 2.1 AA (landing + acervo)

Auditoria do frontend `source/` (landing page, galerias, modais, admin).
Data: 2026-10-17 · Escopo: WCAG 2.1 nível AA, critérios aplicáveis a um
site de museu com conteúdo predominantemente visual.

Resumo: **conforme AA nos critérios avaliados** após as correções desta
rodada (lista abaixo). Duas dívidas registradas ao final.

---

## 1. Contraste de cor (SC 1.4.3 — mínimo 4.5:1 texto normal, 3:1 texto grande)

Razões computadas com a fórmula oficial de luminância relativa, com
composição alfa sobre o fundo `--ink` (#0e0d0b):

| Par (texto / fundo) | Razão | Veredito |
|---|---|---|
| `--paper` #f3ede2 / ink | 16.67:1 | AA |
| `--paper-dim` α=0.62 / ink | 6.75:1 | AA |
| `--paper-faint` α=0.38 → **0.55** / ink | 3.20 → **5.52:1** | **corrigido** |
| `--bronze` #b98a4a / ink | 6.29:1 | AA |
| `--gold` #d8b878 / ink | 10.22:1 | AA |
| `--ink` / `--paper` (cartões claros) | 16.67:1 | AA |
| bronze / paper | 2.65:1 | não usado para texto |

**Correção aplicada:** `--paper-faint` subiu de α=0.38 para α=0.55
(`source/assets/css/style.css`). O piso de 0.55 está documentado em
comentário na variável — abaixo de ~0.50 o texto pequeno fica sob 4.5:1.
A variável alimenta ~20 usos (rótulos em caixa-alta de 10–13px, notas,
hints, preços); todos agora em AA.

## 2. Texto alternativo (SC 1.1.1)

| Elemento | Estado |
|---|---|
| Imagens de skin/cenário (`applySkin`) | `alt=""` — decorativas, correto |
| Lightbox (`#lbImg`) | `alt` = título da peça, atribuído no JS |
| Popup de parede (`#wfImg`) | `alt` = título da peça, atribuído no JS |
| Imagem do item no admin (`#ipImg`) | **corrigido** — `alt` passou a receber o título ao selecionar o item |
| Vídeo do hero | `aria-hidden="true"` — decorativo, correto |

## 3. Teclado (SC 2.1.1, 2.1.2)

- `Escape` fecha todos os overlays (lightbox, viewer 3D, popup de parede,
  login, carrinho, chat) — `main.js`.
- `←`/`→` navegam o popup de parede.
- Hotspots da sala (`wall-spot`) respondem a `:focus-visible` com o mesmo
  realce do `:hover`.
- Nenhuma armadilha de teclado identificada.

## 4. Indicador de foco (SC 2.4.7)

- Inputs de formulário e chat trocam a cor da borda em `:focus`
  (dourado 0.5–0.55 sobre fundo escuro — contraste 3:1+ contra o fundo).
- Hotspots com `:focus-visible` explícito.

## 5. Estrutura e semântica (SC 1.3.1, 4.1.2)

- Um `h1` único; seções com `h2`; modais rotulados.
- **Corrigido:** todos os overlays receberam `role="dialog"` +
  `aria-modal="true"` + rótulo (`aria-label`/`aria-labelledby`):
  lightbox, popup de parede, viewer 3D, login, carrinho, chat.
- **Corrigido:** botões de fechar "×" receberam `aria-label` (antes só
  o glifo, nome acessível vazio): lightbox, popup, viewer, carrinho, chat.
- Formulários com `<label for>` em todos os campos (login, nova coleção,
  novo item, admin). **Corrigido:** os dois inputs sem label visível
  (assistente do hero e chat) receberam `aria-label`.
- Botões de zoom do lightbox nomeados via `title`.

## 6. Dívidas registradas (não bloqueiam AA, tratamento futuro)

1. **Ordem de headings**: painéis/modais usam `h4` sob `h2` (pulo de
   nível — melhor prática, não reprova AA). Trocar por `h3` exige ajuste
   de CSS correspondente; fica para a próxima revisão de estilo.
2. **Focus trap nos modais**: o foco não fica contido dentro do modal
   aberto (Tab pode ir para o fundo da página). AA não exige
   estritamente, mas é recomendado; implementar com `inert` no conteúdo
   de fundo na revisão de JS.

## 7. Multi-idioma

A interface do template é em inglês; o conteúdo (fichas, coleções) segue o
idioma do museu. Tradução da interface é o módulo pago **m-multilingual**,
não implementado — fora do escopo AA (idioma declarado: verificar
`<html lang>` no build do cliente).
