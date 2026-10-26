# Painel SFN — Instituições Financeiras do Banco Central

**Data:** 2026-10-24 (atualizado em 2026-10-25)
**Status:** hub em operação — 11 domínios; integradas as ondas Crédito/SGS, **SCR**
(carteira por modalidade/UF/cliente), Tarifas, taxas de juros por modalidade, séries
macro do SGS, **cruzamento de arranjos (PIX × STR/RSFN × COMPE)** e **Supervisão &
Eventos** (comunicados/eventos de instituições + regimes especiais + penalidades) e
**Conduta** com histórico de 8 trimestres, filtros e drill-down. COPOM removido (fora de
escopo). Desempenho otimizado (índice coberto + gzip + cache). Busca genérica de
resoluções/circulares: parcial (API de baixa qualidade). Nucléa/boleto: sem dado público
estruturado (ver "Fora de escopo").

## Objetivo

Painel analítico local para explorar **toda a base aberta do Banco Central** sobre
instituições financeiras: muito além do balanço básico — indicadores prudenciais,
rentabilidade, carteira de crédito detalhada, reclamações, taxas de juros, cadastro e
PIX — com **histórico** e **perfil completo por instituição** (drill-down), em uma
interface densa (estilo terminal financeiro) com hierarquia visual profissional.

## Arquitetura

App **local ao vivo**: backend Python busca dados nas APIs abertas do BCB, guarda em
cache SQLite e serve um frontend SPA. O usuário roda por duplo-clique (`start.bat`) e
acessa em `http://localhost:8765` (varre portas livres a partir dessa). Nada sai da máquina.

```
bcb-dashboard/
  backend/
    app.py            # servidor stdlib (http.server): API JSON + serve o frontend
    db.py             # camada SQLite (cache + histórico)
    pipeline.py       # orquestra coleta -> cache
    coletores/
      ifdata.py       # Olinda IFDATA: cadastro + 16 relatorios, por AnoMes
      participantes.py # ParticipantesSTR.csv: diretorio da RSFN
      spi.py          # Olinda SPI: PIX liquidados por dia
      taxas.py        # Olinda taxaJuros v2: imobiliario + ConsultaUnificada (todas modalidades)
      reclamacoes.py  # RDR/BCB: ranking de reclamacoes (trimestral)
      focus.py        # Olinda Expectativas: boletim Focus
      cnpj.py         # BrasilAPI: dados cadastrais de CNPJ (ao vivo)
      credito.py      # SGS: credito agregado do SFN (saldo/juros/inadimplencia)
      tarifas.py      # Olinda Informes: tarifas de servicos por instituicao/grupo
      sgs_macro.py    # SGS: Selic, IPCA, IGP-M, cambio (dolar/euro), PIB mensal
      pix_participantes.py # Pix_DadosAbertos: diretorio de participantes do PIX
      supervisao.py   # regimes_especiais + Gepad (penalidades sancionador)
      scr.py          # SCR por sub-regiao: carteira por modalidade/UF/cliente
      eventos.py      # Comunicados do BCB sobre instituicoes (exibeoutrasnormas)
    testes/test_hub.py # bateria (68 testes)
  frontend/
    index.html, styles.css, app.js, charts.js, api.js, util.js
    vendor/echarts.min.js   # vendorizado (offline)
  dados/bcb.db        # cache SQLite (gerado)
  start.bat           # sobe servidor + abre navegador
  atualizar.bat       # re-coleta dados
  docs/SPEC.md
```

### Fontes de dados (verificadas ao vivo)

| Domínio | Fonte | Endpoint / dataset |
|---|---|---|
| Cadastro (CNPJ, conglomerado, situação, segmento, UF) | Olinda IFDATA | `IfDataCadastro(AnoMes=)` |
| 16 relatórios (Resumo, Ativo, Passivo, DRE, Capital/Basileia, Carteira por risco/indexador/região/modalidade/CNAE/porte, Câmbio) | Olinda IFDATA | `IfDataValores(AnoMes=,TipoInstituicao=,Relatorio=)` |
| Taxas de juros por instituição e modalidade (todas as modalidades de crédito, PF/PJ) | Olinda taxaJuros v2 | `ConsultaUnificada` + `TaxasJurosMensalPorMes` (imobiliário) |
| Reclamações (ranking, 8 trimestres de histórico) | RDR/BCB | `rdrweb/rest/ext/ranking` |
| Comunicados do BCB sobre instituições (eventos) | BCB (site) | `api/conteudo/app/normativos/exibeoutrasnormas?p1=Comunicado&p2=<n>` |
| PIX liquidados (diário) | Olinda SPI | `PixLiquidadosAtual` |
| Participantes da RSFN / STR (TED) + flag COMPE | BCB (CSV) | `ParticipantesSTR.csv` |
| Participantes do PIX (diretório por ISPB) | Olinda Pix_DadosAbertos | `ChavesPix(Data=)` (agregado por ISPB) |
| Instituições em regime especial (liquidação/intervenção/RAET) | Olinda regimes_especiais | `Regimes` |
| Penalidades (processo administrativo sancionador) | Olinda Gepad | `QuadroGeralProcessoAdministrativoSancionador` |
| Expectativas de mercado (Focus) | Olinda Expectativas | `ExpectativasMercadoAnuais` |
| CNPJ (cadastro + sócios) | Receita Federal via BrasilAPI | `api/cnpj/v1/{cnpj}` (ao vivo) |
| Crédito agregado do SFN | SGS/BCB | séries `20539/20540/20541/20634/20714/21082` |
| Carteira de crédito por modalidade/UF/cliente (SCR) | Olinda scr_sub_regiao | `scr_sub_regiao(DataBase=AAAAMM)` |
| Tarifas de serviços | Olinda Informes | `Informes_ListaTarifasPorInstituicaoFinanceira` (por CNPJ/grupo) |
| Indicadores macro observados (Selic, IPCA, IGP-M, câmbio, PIB) | SGS/BCB | séries `432/433/13522/189/1/21619/4380` |

### Cache e histórico

SQLite com tabelas: `cadastro(cod,anomes,...)`, `valores(cod,anomes,tipo,relatorio,grupo,conta,coluna,saldo)`,
`taxas(...)`, `reclamacoes(cnpj,anomes,...)`, `pix(...)`, `meta(fonte,ult_atualizacao)`.
Default: **últimos 5 anos (trimestral)**. Primeira execução baixa; depois serve do cache.

## Frontend — denso + drill-down

Tema escuro, alta densidade, `tabular-nums`, hierarquia forte (números-herói, seções,
cromo discreto). Paleta validada do guia de dataviz. Gráficos com ECharts vendorizado
local + tiles/tabelas à mão.

**Visões (sidebar):**
1. **Visão Geral do SFN** — KPIs do sistema, concentração (share S1), treemap por
   segmento, distribuição por UF, séries históricas agregadas.
2. **Explorar Instituições** — tabela densa (dezenas de colunas: balanço + Basileia +
   ROE/ROA + reclamações), filtros avançados, ordenação, densidade ajustável.
3. **Perfil da Instituição** (drill-down) — cabeçalho + seções Balanço · Capital/Basileia ·
   Rentabilidade · Carteira de crédito · Reclamações · Taxas · Séries históricas.
4. **Comparar** — 2 a 5 instituições lado a lado.
5. **Rankings** — maiores ativos, mais reclamadas, melhor Basileia, maior ROE.

## Fases

- **Fase 1:** backend coletor + cache + API (cadastro, Resumo, Capital) — base funcional.
- **Fase 2:** shell do frontend + Visão Geral + Explorar (tabela densa). ← primeiro "ver rodando".
- **Fase 3:** Perfil drill-down + séries históricas.
- **Fase 4:** Reclamações + Taxas + Comparar + Rankings.

## Decisões técnicas

- **Backend somente stdlib** (`http.server` + `sqlite3` + `urllib`) — zero
  dependências `pip`, para o `start.bat` funcionar só com Python instalado.
- **SQLite** (cache), **ECharts vendorizado local** (gráficos).
- Histórico padrão **5 anos trimestral** (configurável em `config`).
- Execução por **`start.bat`** (cria venv, instala deps, sobe servidor, abre navegador).
- Valores do IF.data via Olinda (`IfDataValores.Saldo`) vêm em **reais** (exibidos direto).
- Crédito SGS: saldo em **R$ milhões** (convertido para reais na exibição); juros e
  inadimplência em **percentual**. Tarifas consultadas **ao vivo por CNPJ** (raiz de 8
  dígitos) e cacheadas; grupos consolidados pré-carregados no cache.

## Desempenho

- **Índice coberto** `idx_val_anomes_cod(anomes, cod, coluna_norm, relatorio, saldo)`
  em `valores`: o pivô de métricas-chave (JOIN `cadastro`×`valores` por período) caiu
  de ~2,0 s para ~0,15 s; `prudencial/overview`, de ~1,0 s para ~0,06 s.
- **`ANALYZE`** ao fim de cada coleta, para o otimizador escolher o índice.
- **gzip** nas respostas (quando o cliente aceita e o corpo passa de 1 KB): a listagem
  de instituições vai de ~2,7 MB para ~0,28 MB na rede.
- **Cache em memória** por período para `registro` e `prudencial/overview` e para o
  conjunto de instituições com balanço (invalidado a cada reinício/recoleta).

## Fora de escopo (por ora)

Autenticação, deploy em nuvem, múltiplos usuários, dados que o BCB não publica
(ex.: dados individuais sigilosos).

**Nucléa / boleto:** não há lista pública estruturada de participantes do boleto.
A Nucléa divulga apenas PDFs e o SLC publicado é de cartões. O painel expõe o flag
COMPE (do arquivo da RSFN) como sinal relacionado, sem afirmar participação na Nucléa.

**COPOM / política monetária:** removido do produto por decisão de escopo (o foco é a
instituição, não a Selic). A meta Selic observada permanece em Indicadores Macro (SGS 432).

**Eventos / comunicados:** os comunicados do BCB saem numerados em sequência e expõem
conteúdo limpo via `exibeoutrasnormas?p1=Comunicado&p2=<n>` (Titulo/Data/Assunto). O coletor
`eventos.py` varre (em paralelo, ~24 s) uma janela dos números mais recentes, classifica por
palavra-chave e mantém só os eventos **de instituição** (cancelamento de autorização,
liquidação, intervenção/RAET, controle societário, dirigentes), descartando os de política
monetária (leilão/swap/TBF). A categoria "Dirigentes" (alto volume e rotineira) vem
desligada por padrão na UI.

**Busca genérica de normativos (resoluções/circulares):** a API `buscanormativos` existe
(~47 mil normas), mas devolve títulos não padronizados (nomes internos), sem data/ementa.
Para não exibir dado de baixa qualidade, o painel só linka a busca oficial (fonte "parcial").

**SCR:** usamos o SCR **por sub-região** (agregado leve, ~1,6 mil linhas/mês via Olinda), não
os microdados brutos do SCR.data (arquivos muito grandes, fora de escopo).
