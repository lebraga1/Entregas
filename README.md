# Indexação Geoespacial e Geometria Computacional Híbrida

**Alunos:** Leônidas Braga e Yuri Viana

## 1. Sobre o projeto

Este projeto implementa uma aplicação web para consultar entregadores próximos a restaurantes em Belo Horizonte. O usuário pode selecionar um restaurante, definir um raio de busca e visualizar no mapa os entregadores encontrados, além de consultar as distâncias e os tempos estimados de deslocamento.

A solução utiliza Geohash para representar coordenadas geográficas em formato textual e uma Trie compacta para indexar essas representações e recuperar candidatos por prefixo. Em seguida, os candidatos são filtrados pela distância geográfica e, quando existe uma rota viável, têm suas distâncias e seus tempos de deslocamento estimados utilizando a rede de ruas.

O projeto também utiliza dados de restaurantes obtidos de uma base local e a rede viária do OpenStreetMap. Mecanismos de cache evitam repetir operações de obtenção de dados e geocodificação desnecessariamente.

## 2. Tecnologias utilizadas

| Tecnologia | Finalidade |
|---|---|
| Python | Implementação dos algoritmos e da aplicação. |
| NumPy | Operações numéricas e manipulação das coordenadas dos nós da rede viária. |
| OSMnx | Obtenção, processamento e análise da rede viária do OpenStreetMap. |
| Dash | Construção da interface web e gerenciamento das interações. |
| Dash Leaflet | Exibição do mapa, marcadores e regiões de busca. |
| pytest | Execução dos testes automatizados. |

Os dados da rede viária são obtidos do OpenStreetMap por meio do OSMnx. O primeiro carregamento pode exigir acesso à internet. Os dados armazenados em cache podem ser reutilizados em execuções posteriores.

## 3. Estrutura do projeto

```text
.
├── src/
│   ├── geohash.py
│   ├── trie.py
│   ├── busca_espaco.py
│   ├── distancia.py
│   ├── gera_entregadores.py
│   └── interface.py
├── tests/
│   ├── teste_geohash.py
│   ├── teste_trie.py
│   ├── test_busca_espaco.py
│   ├── benchmark.py
│   └── benchmark_busca.py
├── bares.csv
├── bares_geocodificados.csv
├── app.py
├── requirements.txt
└── README.md
```

### Responsabilidade dos módulos

- **`geohash.py`:** implementa a codificação das coordenadas geográficas.
- **`trie.py`:** implementa a Trie compacta e suas operações.
- **`busca_espaco.py`:** constrói o índice espacial, identifica candidatos e realiza a filtragem geográfica.
- **`distancia.py`:** calcula a distância geográfica entre duas posições utilizando a fórmula de Haversine.
- **`gera_entregadores.py`:** gera a frota sintética, carrega a rede viária e calcula estimativas de rotas.
- **`interface.py`:** implementa a aplicação web, os controles de consulta, o mapa e a apresentação dos resultados.
- **`bares.csv`:** contém a base de restaurantes utilizada na aplicação.
- **`bares_geocodificados.csv`:** armazena os resultados persistidos da geocodificação dos restaurantes.

## 4. Representação geográfica com Geohash

A função principal de codificação é:

```python
geohash(coordenadas, precision=8)
```

A função recebe uma posição geográfica, representada por uma tupla de latitude e longitude, e uma precisão que determina o comprimento do código produzido.

O Geohash divide recursivamente os intervalos de latitude e longitude e representa os intervalos resultantes utilizando caracteres de uma base de 32 símbolos. Quanto maior a precisão, menor tende a ser a região geográfica representada pelo código.

Códigos Geohash com prefixos comuns geralmente representam posições na mesma região. Essa propriedade permite organizar os entregadores e consultar grupos de localizações por prefixo.

Entretanto, duas posições próximas podem estar em lados opostos de uma fronteira entre células. Por isso, uma consulta espacial precisa considerar as células vizinhas que possam intersectar a região pesquisada.

## 5. Trie compacta

A Trie compacta é a estrutura de dados utilizada para indexar os códigos Geohash dos entregadores. Seu objetivo é permitir a recuperação dos identificadores associados a chaves que correspondem a um determinado prefixo.

### 5.1. Estrutura interna

Em vez de armazenar um caractere por aresta, a Trie compacta pode armazenar sequências de caracteres em um único rótulo. Isso reduz a quantidade de nós necessários em caminhos sem ramificações.

Na implementação, a classe `CompactTrie` associa valores às chaves. Nesse projeto, os valores correspondem aos identificadores dos entregadores. Uma chave pode estar associada a vários valores caso diferentes registros possuam o mesmo Geohash.

| Operação | Descrição |
|---|---|
| `insert(key, value)` | Insere uma chave e associa um valor a ela. |
| `search_prefix(prefix)` | Recupera os valores associados às chaves que começam com o prefixo consultado. |
| `contains(key)` | Verifica a existência de uma chave. |
| `remove(key, value)` | Remove uma associação entre chave e valor. |
| `clear()` | Limpa as entradas da estrutura. |

### 5.2. Inserção e divisão de arestas

Durante a inserção, o algoritmo compara a chave com os rótulos das arestas existentes e determina o maior prefixo comum.

Há três situações principais:

1. **Não existe uma aresta compatível:** cria-se uma nova aresta contendo a parte restante da chave.
2. **A aresta corresponde ao trecho atual da chave:** a inserção prossegue no nó seguinte, processando apenas os caracteres ainda não consumidos.
3. **A chave e o rótulo divergem no meio da aresta:** a aresta é dividida no ponto de divergência, e os sufixos são organizados em ramificações separadas.

A implementação utiliza recursão para processar os trechos restantes da chave. Cada chamada trabalha a partir do nó atual e delega a continuação da inserção ao próximo nó quando necessário.

### 5.3. Busca por prefixo

A operação `search_prefix(prefix)` é central para a aplicação. Ela percorre a Trie até localizar o prefixo solicitado e, em seguida, coleta os valores associados às chaves da subárvore correspondente.

A busca considera três casos:

- **Correspondência inexistente:** retorna uma lista vazia.
- **Prefixo termina em um nó:** coleta os valores do nó e de seus descendentes.
- **Prefixo termina no interior de um rótulo:** se todos os caracteres do prefixo corresponderem ao início do rótulo, coleta os valores da subárvore abaixo dessa aresta.

A localização do prefixo e a coleta dos resultados são operações distintas. A primeira percorre o caminho até a região relevante da árvore; a segunda visita os nós necessários para recuperar os identificadores.

### 5.4. Complexidade temporal

Considere:

- \(N\): quantidade de chaves armazenadas;
- \(L\): comprimento da chave ou do prefixo;
- \(S\): custo de percorrer a subárvore e coletar os resultados.

| Operação | Complexidade temporal aproximada |
|---|---|
| Inserção | \(O(L)\), sob hipóteses de acesso eficiente às ramificações e comparação linear dos caracteres. |
| Busca por chave exata | \(O(L)\), sob as mesmas hipóteses. |
| Busca por prefixo | \(O(L + S)\), incluindo a coleta dos resultados. |
| Remoção | \(O(L)\) para localizar a chave, mais o custo de reorganização da árvore. |
| Limpeza | Depende da implementação; redefinir a raiz pode ser \(O(1)\), enquanto liberar explicitamente todos os nós custa \(O(N)\). |

Esses valores descrevem o custo assintótico esperado das operações, não garantem que a Trie seja mais rápida do que uma varredura sequencial em Python. A quantidade de prefixos consultados, os nós visitados, os valores coletados e as estruturas intermediárias também afetam o tempo real.

Na busca por prefixo, o custo depende da quantidade de resultados: se milhares de registros correspondem à consulta, é necessário percorrer a região da árvore que contém esses registros.

### 5.5. Complexidade espacial

Para \(N\) chaves de comprimento máximo \(L\), o tamanho total dos caracteres armazenados é limitado por \(O(NL)\). A Trie compacta pode reduzir a quantidade de nós em relação a uma Trie convencional, especialmente quando há sequências longas sem ramificações.

O índice utilizado pela aplicação também mantém um dicionário que associa os identificadores aos registros completos. Portanto, o espaço total depende tanto da estrutura da Trie quanto da quantidade de registros e dos dados armazenados no dicionário.

### 5.6. Construção do índice espacial

A função `construir_indice(entregadores)` insere o Geohash de cada entregador na Trie e associa a chave ao identificador do registro. Paralelamente, constrói um dicionário `por_id`, que permite recuperar as informações completas de cada entregador.

O índice resultante possui duas partes:

- **Trie:** recupera identificadores a partir de prefixos geográficos.
- **Dicionário `por_id`:** recupera os registros completos a partir dos identificadores.

A construção do índice é realizada antes das consultas e o resultado pode ser reutilizado em diversas buscas. Assim, seu custo deve ser medido separadamente do custo de consulta.

## 6. Dados geográficos e mecanismos de cache

A aplicação utiliza duas fontes distintas de dados geográficos: uma base de restaurantes e a rede viária. Como as duas fontes possuem características diferentes, seus mecanismos de cache também são distintos.

### 6.1. Cache persistente dos restaurantes

A base `bares.csv` contém os dados dos restaurantes utilizados pela aplicação. Os registros não necessariamente possuem coordenadas geográficas prontas para uso no mapa, de modo que a aplicação precisa geocodificar os endereços.

A geocodificação é realizada por meio do Nominatim, serviço associado ao OpenStreetMap. Para isso, a aplicação utiliza informações de endereço, incluindo a combinação dos campos `DESC_LOGRADOURO` e `NOME_LOGRADOURO`.

O problema inicial era que os endereços eram geocodificados novamente a cada execução da aplicação. Isso causava solicitações repetidas à rede, aumentava o tempo de inicialização e podia provocar falhas ou limitações de acesso ao serviço de geocodificação.

A solução implementada consiste em persistir os resultados em `bares_geocodificados.csv`.

O funcionamento é o seguinte:

1. A aplicação lê a base original `bares.csv`.
2. Verifica os resultados de geocodificação que já estão armazenados em `bares_geocodificados.csv`.
3. Reutiliza as coordenadas em cache para os registros já geocodificados.
4. Realiza novas consultas ao Nominatim somente para os registros que ainda precisam de coordenadas.
5. Persiste os resultados obtidos para que possam ser reutilizados nas execuções seguintes.

O cache conserva os campos necessários para identificar o registro e recuperar suas coordenadas, incluindo `_id`, `lat` e `lon`. A normalização das informações de endereço e as tentativas alternativas de geocodificação ajudam a lidar com variações na forma como os logradouros são descritos na base original. Também é aplicada uma pausa entre consultas ao serviço externo.

Esse mecanismo diminui a quantidade de solicitações repetidas, reduz o tempo de inicialização e torna o uso da base de restaurantes menos dependente da disponibilidade imediata do serviço de geocodificação.

O cache é persistente: diferentemente de uma variável em memória, o arquivo continua disponível após o encerramento do programa. Se os endereços originais forem alterados ou as coordenadas precisarem ser atualizadas, será necessário invalidar ou atualizar os registros correspondentes no cache.

### 6.2. Cache da rede viária

A rede viária é obtida a partir do OpenStreetMap por meio do OSMnx. Seu carregamento e processamento podem ser custosos, pois envolvem a obtenção de dados geográficos e a preparação de um grafo de ruas.

Para evitar downloads repetidos, a aplicação utiliza a configuração:

```python
ox.settings.use_cache = True
```

O OSMnx pode armazenar respostas obtidas durante o acesso aos seus serviços e reutilizá-las em operações posteriores. Além disso, o módulo `gera_entregadores.py` mantém o grafo carregado na variável global `_GRAFO`, acompanhado dos dados auxiliares utilizados para localizar nós próximos.

O grafo em memória é reutilizado durante a execução do programa, evitando reconstruir a estrutura a cada chamada que necessita calcular uma rota. O cache do OSMnx, por sua vez, pode reduzir a necessidade de solicitar novamente dados remotos entre execuções.

O cache não garante que os dados permaneçam permanentemente atualizados. Alterações na rede viária ou nos endereços podem exigir uma atualização explícita.

## 7. Geração da frota sintética

A frota é gerada por meio da função:

```python
gerar_entregadores(restaurantes, quantidade, sigma_km=1.0)
```

O algoritmo gera posições de entregadores como uma distribuição normal baseada na proximidades dos restaurantes. O parâmetro `sigma_km` controla a escala da dispersão espacial.

Como uma posição aleatória pode cair fora de uma via apropriada, o processo utiliza a rede viária para associar os entregadores a nós próximos do grafo. Os registros gerados incluem identificador, latitude, longitude e Geohash.

## 8. Rede viária e estimativa de rotas

A função `carregar_grafo()` obtém a rede viária de Belo Horizonte por meio do OSMnx e prepara os atributos necessários para estimar o tempo de viagem.

São atribuídas velocidades de referência a diferentes categorias de vias para calcular o tempo esperado de entraga. Essas velocidades são aproximações e não incorporam condições de trânsito em tempo real.

### 8.1. Associação de coordenadas aos nós

A função `no_mais_proximo(lat, lon)` identifica o nó da rede viária mais próximo de uma coordenada geográfica. A implementação utiliza arrays NumPy com as coordenadas dos nós e percorre esses dados para determinar o mais próximo.

Esse método evita a necessidade de uma estrutura espacial adicional, mas seu custo cresce linearmente com o número de nós do grafo.

### 8.2. Cálculo de rotas

A função `estimar_rota(...)` associa as posições de origem e destino aos nós mais próximos e procura um caminho utilizando o atributo `travel_time`.

Quando há uma rota válida, são retornadas a distância estimada pela rede viária, em quilômetros, e o tempo estimado de deslocamento, em minutos. Quando não existe uma rota válida, o candidato pode ser descartado.

A distância pela rede viária não é necessariamente igual à distância em linha reta, pois depende das conexões, da topologia da rede e das restrições de circulação.

## 9. Algoritmo de busca espacial

A consulta é implementada em `busca_espaco.py`, por meio da função:

```python
buscar_entregadores(frota, restaurante, raio_km, indice=None)
```

A função recebe a frota, o restaurante selecionado, o raio de busca e, opcionalmente, o índice espacial.

### Etapas da consulta

1. **Preparação:** obtém as coordenadas do restaurante e valida o raio.
2. **Seleção de regiões candidatas:** quando há índice, calcula os prefixos Geohash das regiões que podem intersectar a área de busca.
3. **Busca na Trie:** recupera os identificadores associados aos prefixos.
4. **Recuperação dos registros:** utiliza `por_id` para obter os dados completos dos candidatos.
5. **Filtragem geométrica:** calcula a distância em linha reta e descarta posições fora do raio.
6. **Estimativa de rotas:** calcula distância e tempo de viagem na rede viária para os candidatos restantes.
7. **Ordenação:** organiza os resultados pelo tempo estimado de deslocamento, do menor para o maior.

Quando o índice não é fornecido, a função pode examinar a frota completa. Essa alternativa permite comparar uma consulta indexada com uma busca exaustiva, desde que ambas utilizem os mesmos critérios de filtragem.


### 9.1 Precisão do índice

A implementação utiliza `PRECISAO_INDICE = 5` para selecionar prefixos, enquanto os códigos armazenados podem ter precisão maior. Assim, cada prefixo consultado pode corresponder a vários códigos Geohash mais longos.

A seleção de prefixos deve cobrir todas as células que possam intersectar a região pesquisada. Como as células possuem limites próprios, a filtragem geométrica posterior remove os falsos positivos.

A correção do índice deve ser verificada comparando os resultados da busca indexada com os da busca exaustiva, sobretudo em diferentes raios e nas proximidades das fronteiras das células.

## 10. Interface web

A interface utiliza Dash e Dash Leaflet. O mapa apresenta restaurantes, entregadores e a região de busca em camadas separadas.

A interface permite gerar a frota, selecionar um restaurante, definir o raio e executar a consulta. Os resultados são exibidos no mapa e em uma tabela com identificador do entregador, distância pela rede viária e tempo estimado de deslocamento.

Os resultados são ordenados pelo Tempo Estimado, isto é, pelo tempo estimado de chegada.

O tempo exibido pela interface pode incluir tanto a filtragem espacial quanto o cálculo das rotas dos candidatos. Por isso, ele não deve ser confundido com o tempo isolado de consulta espacial apresentado na seção de avaliação experimental.

## 11. Instalação e execução

### 11.1. Pré-requisitos

É necessário possuir Python em uma versão compatível com as dependências do projeto, `pip` e acesso à internet para obter os dados geográficos que ainda não estejam em cache.

### 11.2. Criar o ambiente virtual

No Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 11.3. Instalar as dependências

```bash
python -m pip install -r requirements.txt
```

### 11.4. Iniciar a aplicação

Execute o aplicativo:

```bash
python -m app.py
```

Depois da inicialização, abra no navegador o endereço local indicado no terminal.

Na primeira execução, a obtenção da rede viária e a geocodificação dos restaurantes que ainda não possuem coordenadas em cache podem aumentar o tempo de inicialização. As execuções seguintes podem reutilizar os dados persistidos e as estruturas em memória.

## 12. Testes automatizados

Os testes automatizados verificam a correção dos algoritmos independentemente da interface.

Execute os testes a partir da raiz do projeto:

```bash
python -m pytest -v
```

### 12.1. Testes do Geohash

- Verificar se coordenadas válidas produzem códigos.
- Verificar se o comprimento corresponde à precisão solicitada.
- Verificar a consistência para coordenadas iguais.
- Testar diferentes regiões e posições próximas aos limites das células.

### 12.2. Testes da Trie

- Inserir e localizar chaves.
- Inserir chaves com prefixos comuns.
- Consultar prefixos existentes e inexistentes.
- Testar prefixos que terminam dentro de rótulos compactados.
- Remover associações e verificar os resultados.
- Limpar a estrutura.

### 12.3. Testes da busca espacial

- Verificar que posições dentro do raio podem ser encontradas.
- Verificar que posições fora do raio são descartadas.
- Comparar a busca indexada com a busca exaustiva.
- Testar raios inválidos e casos de fronteira.
- Verificar candidatos sem rota viável.

### 12.4. Testes de integração

A integração entre frota, índice, rede viária e interface pode ser testada com dados pequenos e controlados. Para testar apenas a lógica espacial, as funções dependentes do OSMnx podem ser simuladas, evitando downloads durante os testes.

## 13. Avaliação experimental

Esta seção apresenta o benchmark da consulta espacial, realizado para comparar a Trie compacta com uma busca exaustiva sobre a frota.

### 13.1. Objetivo e metodologia

O objetivo foi verificar se a indexação por Geohash e Trie reduz o tempo necessário para identificar entregadores dentro de um raio de busca.

Foram comparadas duas estratégias:

- **Consulta indexada:** gera prefixos Geohash, consulta a Trie, reúne os identificadores candidatos e filtra os registros pela distância em linha reta.
- **Busca exaustiva:** percorre toda a frota e aplica o mesmo filtro de distância.

A frota sintética foi gerada com uma semente fixa (`seed=3`) e as consultas utilizaram o centro geográfico \((-19.9191, -43.9386)\), com raio de 2 km. Foram avaliados cinco tamanhos de frota, com dez repetições por estratégia.

O índice foi construído antes da medição e reutilizado nas consultas. O tempo de construção da Trie, o cálculo de rotas e a estimativa de ETA não foram incluídos.

O tempo informado corresponde à mediana das dez medições de cada estratégia. A comparação também verificou se ambas retornavam exatamente os mesmos identificadores.

### 13.2. Resultados

Os resultados obtidos foram:

| Quantidade de entregadores | Resultados após filtragem espacial | Trie (ms) | Busca exaustiva (ms) | Razão Trie / exaustiva |
|---:|---:|---:|---:|---:|
| 1.000 | 117 | 0,789 | 0,381 | 2,07x |
| 5.000 | 529 | 3,509 | 1,946 | 1,80x |
| 10.000 | 1.003 | 8,352 | 3,787 | 2,21x |
| 20.000 | 2.018 | 19,795 | 7,555 | 2,62x |
| 50.000 | 5.133 | 60,322 | 19,808 | 3,05x |

**Correção dos resultados:** em todos os cinco cenários, a consulta indexada e a busca exaustiva retornaram conjuntos idênticos de entregadores.

A razão apresentada corresponde ao tempo da Trie dividido pelo tempo da busca exaustiva. Portanto, valores superiores a 1 indicam que a Trie foi mais lenta no cenário medido.

### 13.3. Interpretação dos resultados

A busca exaustiva foi mais rápida em todos os tamanhos de frota testados. Para 50 mil entregadores, por exemplo, a Trie levou aproximadamente 60,3 ms, enquanto a busca exaustiva levou 19,8 ms.

Embora a Trie tenha reduzido o número de registros submetidos à filtragem final, o custo de consultar a estrutura foi superior à economia obtida. Na maior frota, 5.133 entregadores ficaram dentro do raio de busca, mas a Trie precisou gerar os prefixos, percorrer os nós correspondentes, reunir os identificadores e recuperar os registros antes de calcular as distâncias.

A busca exaustiva, por outro lado, percorreu uma lista e calculou a distância de cada entregador. Essa operação sequencial é simples e possui pouco overhead de estruturas de dados.

Os resultados também mostram que a diferença aumenta nas frotas maiores: a Trie demorou aproximadamente 2,07 vezes o tempo da busca exaustiva para 1.000 entregadores e 3,05 vezes para 50.000. Isso indica que, para essa implementação, a consulta à Trie não compensou o custo de seleção dos candidatos.

### 13.4. O papel da recursão

A implementação recursiva da Trie pode contribuir para o custo, pois cada chamada tem overhead adicional em Python. Além disso, a coleta dos resultados percorre os descendentes da subárvore correspondente.

Entretanto, o benchmark não mede separadamente o custo da recursão. Portanto, não é possível concluir que ela seja a causa principal da diferença.

### 13.5. Relação com o desempenho total da aplicação

Este experimento não inclui o cálculo de rotas. Isso é importante porque o cálculo de ETA pela rede viária pode dominar o tempo total de uma consulta completa.

A avaliação espacial isolada permite observar o custo da estrutura de dados sem que as operações de roteamento ocultem as diferenças. Entretanto, os resultados aqui apresentados não permitem concluir diretamente qual estratégia oferece o menor tempo de resposta para a aplicação inteira.

Uma avaliação completa deve considerar o tempo de seleção espacial, a quantidade de candidatos que precisam de roteamento e o custo de estimar suas rotas.

### 13.6. Conclusão do benchmark

Para os dados sintéticos, o centro geográfico e o raio utilizados, a busca exaustiva foi mais eficiente do que a consulta pela Trie compacta. As duas estratégias produziram os mesmos resultados, mas a indexação adicionou um custo de processamento que não foi compensado pela redução do número de distâncias calculadas.

Isso não significa que uma Trie compacta seja sempre inadequada para consultas espaciais. O resultado depende da implementação, da distribuição dos dados, da resolução do Geohash, da quantidade de prefixos e do número de candidatos recuperados.

Como melhoria futura, seria ideal avaliar as etapas internas da consulta para identificar os custos dominantes e avaliar otimizações antes de alterar a estrutura de dados.

## 14. Limitações

A implementação possui limitações que devem ser consideradas:

- A frota é sintética e não representa necessariamente a distribuição real de entregadores.
- As velocidades atribuídas às vias são aproximações e não representam necessariamente o trânsito em tempo real.
- A distância em linha reta é usada para filtrar candidatos, enquanto a distância pela rede viária é usada nos resultados.
- A precisão do Geohash influencia o número de candidatos recuperados.
- A busca pelo nó viário mais próximo percorre os nós do grafo e pode se tornar custosa em redes grandes.
- A obtenção inicial dos dados geográficos depende da disponibilidade dos serviços externos.
- Os tempos do benchmark refletem o ambiente de execução e os parâmetros utilizados, não uma garantia de desempenho em qualquer frota ou máquina.


## 16. Conclusão

O benchmark da consulta espacial demonstrou que, na implementação e nos cenários testados, a Trie compacta não apresentou vantagem temporal sobre a busca exaustiva. Apesar de recuperar corretamente os mesmos resultados, seu custo de consulta foi maior em todos os tamanhos de frota avaliados.

Esse resultado destaca a importância de avaliar com testes as estruturas de dados,pois apesar da estrutura reduzir o conjunto de registros examinados, ainda assim pode ser mais lenta devido ao overhead de navegação e recuperação de resultados.

## 17. Referências

- OpenStreetMap. https://www.openstreetmap.org/
- OSMnx. Documentação da biblioteca para obtenção, análise e roteamento em redes viárias. https://osmnx.readthedocs.io/
- Nominatim. Documentação do serviço de geocodificação do OpenStreetMap. https://nominatim.org/
- Dash. https://dash.plotly.com/
- Dash Leaflet. https://www.dash-leaflet.com/
- pytest. https://docs.pytest.org/