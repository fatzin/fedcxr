# Bibliotecas do painel (sem CDN)

O painel roda offline: tudo que o navegador carrega vem daqui, servido por `dashboard/server.py` em `/vendor/...`.
Os arquivos são cópias sem alteração dos pacotes publicados no npm. Cada tarball foi baixado de `registry.npmjs.org`
e conferido contra o `shasum` (SHA-1) e o `integrity` (SHA-512) dos metadados do registro antes de copiar.

| Arquivo aqui | Pacote | Arquivo no pacote | Licença |
|---|---|---|---|
| `preact.module.js` | preact 10.26.4 | `dist/preact.module.js` | MIT |
| `preact-hooks.module.js` | preact 10.26.4 | `hooks/dist/hooks.module.js` | MIT |
| `htm.module.js` | htm 3.1.1 | `dist/htm.module.js` | Apache-2.0 |
| `htm-preact.module.js` | htm 3.1.1 | `preact/index.module.js` | Apache-2.0 |
| `signals.module.js` | @preact/signals 1.3.2 | `dist/signals.module.js` | MIT |
| `signals-core.module.js` | @preact/signals-core 1.8.0 | `dist/signals-core.module.js` | MIT |
| `chart.umd.js` | chart.js 4.4.1 | `dist/chart.umd.js` | MIT |

O `index.html` liga os nomes dos módulos a estes arquivos com um import map
(`preact`, `preact/hooks`, `htm`, `htm/preact`, `@preact/signals`, `@preact/signals-core`).
O Chart.js entra como script clássico e expõe `window.Chart`. Os `.map` não foram copiados.

## Origem e verificação

| Pacote | Tarball | shasum (SHA-1) | integrity |
|---|---|---|---|
| preact 10.26.4 | https://registry.npmjs.org/preact/-/preact-10.26.4.tgz | `b514f4249453a4247c82ff6d1267d59b7d78f9f9` | `sha512-KJhO7LBFTjP71d83trW+Ilnjbo+ySsaAgCfXOXUlmGzJ4ygYPWmysm77yg4emwfmoz3b22yvH5IsVFHbhUaH5w==` |
| htm 3.1.1 | https://registry.npmjs.org/htm/-/htm-3.1.1.tgz | `49266582be0dc66ed2235d5ea892307cc0c24b78` | `sha512-983Vyg8NwUE7JkZ6NmOqpCZ+sh1bKv2iYTlUkzlWmA5JD2acKoxd4KVxbMmxX/85mtfdnDmTFoNKcg5DGAvxNQ==` |
| @preact/signals 1.3.2 | https://registry.npmjs.org/@preact/signals/-/signals-1.3.2.tgz | `5f20377cbea55f4d4514f45b9232cb4593e25013` | `sha512-naxcJgUJ6BTOROJ7C3QML7KvwKwCXQJYTc5L/b0eEsdYgPB6SxwoQ1vDGcS0Q7GVjAenVq/tXrybVdFShHYZWg==` |
| @preact/signals-core 1.8.0 | https://registry.npmjs.org/@preact/signals-core/-/signals-core-1.8.0.tgz | `45ffadb81b48a298a4accd26b3f6c0140cd6dacc` | `sha512-OBvUsRZqNmjzCZXWLxkZfhcgT+Fk8DDcT/8vD6a1xhDemodyy87UJRJfASMuSD8FaAIeGgGm85ydXhm7lr4fyA==` |
| chart.js 4.4.1 | https://registry.npmjs.org/chart.js/-/chart.js-4.4.1.tgz | `ac5dc0e69a7758909158a96fe80ce43b3bb96a9f` | `sha512-C74QN1bxwV1v2PEujhmKjOZ7iUM4w6BWs23Md/6aOZZSlwMzeCIDGuZay++rBgChYru7/+QFeoQW0fQoP534Dg==` |

SHA-256 dos arquivos copiados (para conferir depois com `shasum -a 256 dashboard/vendor/*.js`):

```
74401d738dd3e03ee5dfb3b6841210fe2c4ead8a960c4011ca4ba0b78a9fd8f3  chart.umd.js
b3f51db71c12eabba61819feb74ace7cadc2744af41866c3fcad2ab960415746  htm-preact.module.js
ab33dd3f38059b9be4d5f5350128eefb2356639c4e0bbe9d9e8b3ba75847e9e4  htm.module.js
0e62f95470546ddf657f9cf5f84aaf9de01bb869ee742c2095429cd2b4c9ea0f  preact-hooks.module.js
2ce1b7b810fc14cda3f4242e636311b5a5e6d5a6cb1f3274fe948fe3bba3d32e  preact.module.js
04524816f4a89856fe221b9c1debb03711a7c2d32ca6d79f741869b961b330da  signals-core.module.js
ba022cd8b6df8baeec9c43c0c27ea6b8dfac8258f7754ad49a97bc4933dc698e  signals.module.js
```

## Fontes

Geist e Geist Mono continuam vindo do Google Fonts pelo `<link>` do `index.html`. Sem internet, o navegador usa as
fontes de reserva da pilha (`ui-sans-serif`, `system-ui`, `ui-monospace`, Menlo); nada quebra.

## Licenças

Os textos completos estão em `licenses/`: `preact.LICENSE`, `preact-signals.LICENSE` e `preact-signals-core.LICENSE`
(MIT, Preact Team e Jason Miller), `chart.js.LICENSE.md` (MIT, Chart.js Contributors) e `htm.LICENSE` (Apache 2.0, Google).
