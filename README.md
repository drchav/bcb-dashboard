# Painel SFN — Instituições Financeiras do Banco Central

Painel local para explorar os dados abertos do Banco Central sobre todas as
instituições do Sistema Financeiro Nacional: balanço, capital/Basileia,
rentabilidade, segmentação (S1–S5), com **histórico trimestral** e **perfil
completo por instituição**.

---

## ▶ Como usar (duplo-clique)

1. **Abrir o painel:** dê **duplo-clique em `start.bat`**.
   - Abre uma janelinha preta e, em seguida, o **navegador sozinho** em
     `http://localhost:8765`.
   - Na **primeira vez** ele baixa os dados do Banco Central (alguns minutos,
     precisa de internet). Depois abre na hora, do cache local.
2. **Fechar:** feche a janelinha preta.
3. **Atualizar os dados** (quando quiser dados mais novos): duplo-clique em
   **`atualizar.bat`**.
4. **Baixar TUDO** (5 anos de histórico + os 16 relatórios, incluindo carteira
   de crédito por risco/modalidade/CNAE/região): duplo-clique em
   **`baixar-TUDO (modo completo).bat`** (demora 10–20 min) e depois abra com
   `start.bat`.

> Tudo roda **só no seu PC** (`localhost`). Nada é publicado na internet.

---

## O que dá para ver (hub por domínios)

> **Ajuda em cada canto:** ao lado de praticamente cada título, KPI, filtro e
> coluna há um ícone **“ⓘ”**. Passe o mouse (ou dê foco pelo teclado) para ver,
> em linguagem simples, **de onde vem aquele dado, como ele é calculado e o que
> significa** — inclusive dent  ro do perfil de cada instituição.

O sistema é um **hub do Sistema Financeiro Nacional**, organizado por domínios
(a segmentação S1–S5 é apenas um recorte dentro de "Prudencial", não o centro):

1. **Panorama** — visão macro: instituições por tipo/grupo, ativo total, crédito,
   participantes da RSFN e estatísticas do PIX do dia.
2. **Instituições** *(espinha dorsal)* — registro central de **todas** as
   instituições por tipo/hierarquia (bancos, cooperativas, financeiras,
   corretoras/distribuidoras, consórcios, instituições de pagamento,
   desenvolvimento). Filtros por grupo, UF, controle, situação, individual/
   conglomerado, com/sem balanço e por **arranjo**: no **PIX**, no **STR/TED
   (RSFN)**, com **conexão RSFN direta** e na **COMPE**. Também por
   **participação no SPI (Direta × Indireta)** e por **autorização** —
   *Autorizadas pelo BCB*, *Não sujeitas a autorização* (IPs de propósito
   limitado) ou *Sujeitas mas ainda não autorizadas* (em adesão) — a partir da
   **Lista de participantes do Pix**. Cada linha mostra os arranjos e a
   participação/autorização, e abre um **perfil unificado**.
3. **Pagamentos (PIX, RSFN/STR & arranjos)** — série diária de PIX liquidados no
   SPI, o diretório de participantes da RSFN e uma **matriz de participação** que
   cruza por ISPB quem está no **PIX**, no **STR/TED**, com **RSFN direta** e na
   **COMPE** (com as interseções: "no PIX e RSFN direta", "no PIX mas não no STR" etc.).
4. **Crédito (SFN)** — crédito agregado do sistema (séries mensais do SGS): saldo da
   carteira total, PF e PJ, concessões, **taxa média de juros** e **inadimplência**;
   a **carteira detalhada pelo SCR** (por modalidade, UF e PF/PJ, com inadimplência —
   ex.: Habitacional, Cartão, Rural, Consignado); e as **taxas de juros por modalidade**
   (crédito pessoal, consignado, veículos, cartão, cheque especial, capital de giro…)
   com a faixa de taxas por instituição.
5. **Tarifas de serviços** — tarifas padronizadas por **grupo consolidado** e por
   **instituição** (consulta ao vivo por CNPJ, com valores máximos e vigências).
6. **Cooperativismo** — recorte do registro para o sistema cooperativo.
7. **Prudencial & Saúde** — balanço, capital/Basileia, rentabilidade e a
   **segmentação S1–S5** (aqui, como recorte).
8. **Conduta & Reclamações** — ranking de reclamações por instituição com **histórico
   de 8 trimestres**: posição, índice, reclamações, procedentes, **% de procedência**,
   clientes e um **sparkline de evolução** do índice. Filtros (Top 15 / Demais / só com
   índice + busca) e **linhas clicáveis** que abrem o perfil completo da instituição —
   lá a série histórica do índice aparece no cartão de reclamações.
9. **Supervisão & Eventos** — atos do BCB sobre instituições: **comunicados/eventos**
   (intenção de cancelar autorização, decretação de liquidação, intervenção/RAET,
   mudança de controle societário, posse/eleição de dirigentes) com **link direto** para
   cada comunicado e filtro por tipo; **regimes especiais** (liquidação, intervenção,
   RAET) — cada linha **expande** para ver liquidante, endereço, CEP e contatos, e abre
   o perfil da instituição — e **penalidades** do processo administrativo sancionador (multas,
   inabilitações), por CNPJ. (Ficam de fora os comunicados de política monetária —
   leilões, swap, TBF.)
10. **Indicadores Macro** — projeções do boletim **Focus** (Selic, IPCA, câmbio, PIB)
    e as **séries observadas** do SGS (meta Selic, IPCA e IGP-M, dólar e euro, PIB mensal).
11. **Fontes de dados** — catálogo de todas as fontes com **link direto** para a API
    e a página oficial (para comprovar a origem).

### Modal da instituição (clique em qualquer linha)

Abre um painel com **tudo sobre a instituição**, em abas:
- **Visão geral & Financeiro** — KPIs, séries históricas, demonstrativos conta a
  conta e reclamações.
- **Identificação (CNPJ)** — consulta **ao vivo** à Receita Federal (via BrasilAPI):
  razão social, situação cadastral, CNAE, capital social, endereço, quadro de sócios.
- **Taxas de juros** — taxas praticadas pela instituição em **todas as modalidades de
  crédito** (PF e PJ: crédito pessoal, consignado, veículos, cartão, cheque especial,
  capital de giro etc.) e no financiamento imobiliário, com o ranking entre instituições.
- **Tarifas de serviços** — tarifário padronizado da instituição (consulta ao vivo
  por CNPJ: serviço, unidade, valor máximo e vigência).
- **Fontes & Links** — links diretos para IF.data, consulta CNPJ e busca do site
  institucional.

No topo do perfil aparecem os **arranjos** da instituição (PIX, STR/TED, RSFN direta)
e avisos de **supervisão** (regime especial e penalidades), quando houver.

## Testes

Duplo-clique em **`rodar-testes.bat`** para rodar a bateria de testes. Ela valida
os endpoints, as agregações e **todos os tipos de instituição** (não só
cooperativas): bancos, cooperativas, financeiras, corretoras, consórcios,
instituições de pagamento e de desenvolvimento.

---

## Requisitos

- **Python 3** instalado (o `start.bat` detecta `python` ou `py`).
- Internet apenas na primeira coleta e nas atualizações.
- Backend usa **somente a biblioteca padrão do Python** — não precisa instalar
  nada com `pip`.

## Fontes de dados (todas públicas e oficiais)

Integradas (com link direto na aba **Fontes de dados** do painel):
- **IF.data (Olinda/BCB)** — cadastro, balanço, capital e segmentação, com histórico.
- **ParticipantesSTR.csv (BCB)** — diretório da RSFN (ISPB, código COMPE, acesso).
- **SPI (Olinda/BCB)** — PIX liquidados por dia.
- **Participantes do PIX (Pix_DadosAbertos/BCB)** — diretório de instituições no arranjo PIX (por ISPB/segmento).
- **Lista de participantes do Pix (BCB)** — por instituição: participação no SPI (direta/indireta), se é autorizada pelo BCB, se é sujeita ou não à autorização, modalidade (Provedor de Conta Transacional / Iniciador) e situação (ativo / em adesão).
- **Regimes especiais (Olinda/BCB)** — instituições em liquidação, intervenção ou RAET.
- **Processo sancionador — Gepad (Olinda/BCB)** — penalidades aplicadas a instituições.
- **Comunicados do BCB (site/BCB)** — eventos de instituições (cancelamento de autorização,
  liquidação, intervenção/RAET, controle societário, dirigentes), por número de comunicado.
- **taxaJuros (Olinda/BCB)** — taxas de juros por instituição em todas as modalidades
  de crédito (PF/PJ) e no financiamento imobiliário.
- **Ranking de reclamações (RDR/BCB)** — reclamações por instituição.
- **Expectativas de Mercado / Focus (Olinda/BCB)** — projeções Selic, IPCA, câmbio, PIB.
- **SGS — séries macro (BCB)** — meta Selic, IPCA (mensal e 12m), IGP-M, câmbio (dólar/euro) e PIB mensal.
- **CNPJ (Receita Federal via BrasilAPI)** — dados cadastrais e sócios.
- **Crédito agregado (SGS/BCB)** — saldo (total/PF/PJ), concessões, juros e inadimplência.
- **SCR por sub-região (Olinda/BCB)** — carteira de crédito por modalidade, UF e PF/PJ, com vencido/inadimplência.
- **Tarifas de serviços (Informes/BCB)** — tarifário por instituição e por grupo consolidado.
- **COPOM (API do site do BCB)** — comunicados e atas das reuniões.

Parcial / não viável (documentado na aba **Fontes**):

> **Busca de normativos (resoluções/circulares):** os **comunicados sobre instituições**
> (cancelamento de autorização, liquidação etc.) **já estão integrados** em Supervisão &
> Eventos (via `exibeoutrasnormas`, conteúdo limpo). O que segue parcial é a busca genérica
> de **resoluções/circulares**: a API `api/search/app/normativos/buscanormativos` (~47 mil
> normas) devolve títulos não padronizados (nomes internos de arquivo), sem data/ementa
> estruturadas; para não exibir dado de baixa qualidade, apenas **linkamos a busca oficial**.

> **Nucléa / boleto:** não há lista pública **estruturada** de participantes de boleto.
> O boleto é liquidado no **SILOC** (o "SLC" divulgado é de **cartões**); a Nucléa só
> publica PDFs e **bloqueia download automatizado** (HTTP 403/WAF). Por isso o painel
> expõe o flag **COMPE** (da RSFN) como sinal relacionado, deixando claro que **não** é
> a lista de participantes de boleto da Nucléa.

Valores monetários em reais.

## Desempenho

As páginas carregam rápido mesmo com a base cheia (>1,6 mi de linhas de balanço):
- índice coberto em `valores` que acelera o pivô de métricas (~2s → ~0,15s);
- `ANALYZE` após cada coleta (ajuda o otimizador do SQLite);
- respostas **comprimidas com gzip** (a listagem de instituições cai de ~2,7 MB para ~0,28 MB);
- cache em memória dos recortes mais pesados (reaproveitado entre navegações).

## Servidor online — https://bcb.dlip.com.br

O painel também roda no droplet `backoffice.dlip.com.br`, com
**login obrigatório**. O `start.bat` local continua sem login (`BCB_AUTH=0`).

- **Arquitetura:** Cloudflare (HTTPS, SSL *Flexible*) → nginx :80
  (`/etc/nginx/sites-available/bcb.conf`) → `python3 app.py` em `127.0.0.1:8765`
  (serviço systemd `bcb-dashboard`, usuário de sistema `bcb`). Código em
  `/srv/bcb-dashboard`.
- **Usuários:** ficam em `dados/usuarios.db` (separado do `bcb.db`), só no
  servidor. Senhas com PBKDF2-SHA256, sessão de 7 dias em cookie HttpOnly,
  bloqueio após 10 tentativas erradas em 15 min. Administradores cadastram,
  desativam, redefinem senha e excluem usuários em **/usuarios**; qualquer
  usuário troca a própria senha pelo link "Senha" na barra lateral.
  Criar/resetar um admin pelo terminal:
  `ssh root@<servidor> 'cd /srv/bcb-dashboard/backend && runuser -u bcb -- python3 auth.py criar-admin email@x.com'`
- **Atualização diária:** timer `bcb-dashboard-atualizar.timer` às 06:30 (Brasília).
  Coleta numa cópia do banco, confere a integridade e só então troca e reinicia o
  painel — se o BCB falhar, o painel segue com os dados anteriores (o banco antigo
  fica em `dados/bcb.db.anterior`). Logs: `journalctl -u bcb-dashboard-atualizar`.
  Rodar na hora: `systemctl start bcb-dashboard-atualizar`.
- **Publicar mudanças:** crie `deploy/deploy.env` (fora do git) com
  `SERVIDOR=root@<ip-do-servidor>` e rode `./deploy/deploy.sh` (código) ou
  `./deploy/deploy.sh --com-banco` (também envia o `dados/bcb.db` local).

Variáveis de ambiente (`backend/config.py`): `BCB_AUTH`, `BCB_HOST`, `BCB_PORTA`,
`BCB_PORTA_FIXA`, `BCB_ABRIR_NAVEGADOR`, `BCB_COOKIE_SEGURO`, `BCB_DB_PATH`,
`BCB_AUTH_DB_PATH`, `BCB_MODO`.

## Estrutura

```
backend/   servidor (stdlib) + coletores + cache SQLite + auth.py (login)
frontend/  interface (HTML/CSS/JS + ECharts vendorizado offline) + login/usuarios
dados/     bcb.db (cache gerado; pode ficar grande no modo completo), usuarios.db
deploy/    systemd (servico + timer diario), nginx, deploy.sh, atualizar-servidor.sh
docs/      SPEC.md
```

## Dica

O cache (`dados/bcb.db`) pode ocupar centenas de MB (modo rápido) ou vários GB
(modo completo). Para recomeçar do zero, apague `dados/bcb.db` e rode `start.bat`.
