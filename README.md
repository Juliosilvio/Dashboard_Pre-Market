# Dashboard Pre-Market

Dashboard no navegador para estudo de cenários e apoio à decisão de posição em
dois ativos futuros (Índice e Dólar e outros ativos de forex e indices internacionais), cruzando sinais de múltiplos ativos e
múltiplos timeframes (MTF) antes e durante o pregão.

A ideia central: em vez de olhar o ativo isoladamente, o sistema acompanha um
conjunto de referências (juros, câmbio, curva de juros, notícias, correlação e
causalidade entre ativos) para montar um cenário de pré-mercado e sinalizar qual
posição (Índice ou Dólar) tende a fazer mais sentido no dia.

> Este repositório é uma versão de portfólio: trechos sensíveis (credenciais,
> conexões específicas, fontes de dado pontuais) foram removidos ou
> generalizados. O projeto completo roda localmente, conectado ao MetaTrader 5.

## Demonstração

[▶ Assistir ao vídeo de demonstração](https://github.com/Juliosilvio/Dashboard_Pre-Market/blob/main/demo.mp4)

(abre a própria página do GitHub com o player — não baixa o arquivo)

## Estrutura

```
backend/
  scripts_py/   # coleta, indicadores, correlação/causalidade, modelos de swing,
                # vieses direcional e overnight, sinais de pré-abertura
frontend/
  src/          # painel React (Vite) que consome os dados do backend
```

## Backend

Scripts Python responsáveis por:

- Coletar e alinhar dados históricos e em tempo real em múltiplos timeframes
- Calcular indicadores técnicos e estatísticos (amplitude, desvios, causalidade,
  correlação, GARCH, classificador de swing)
- Cruzar ativos de referência (juros, câmbio, curva de juros, notícias) para
  montar o cenário de pré-abertura
- Gerar os arquivos de saída (`json/last_json/`) que alimentam o frontend

## Frontend

Painel em React + Vite (`painel-indice-dolar-frontend`) que lê os dados gerados
pelo backend e exibe os cards de cenário: cotações, viés direcional, curva de
juros, correlação/causalidade, modelo de swing e notícias relevantes do dia.

```
cd frontend
npm install
npm run dev
```

## Status

Projeto em desenvolvimento contínuo, de uso pessoal.
