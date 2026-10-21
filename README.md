# Indexação Geoespacial e Geometria Computacional Híbrida



**Alunos:** Leônidas Braga e Yuri Viana



## 1. Sobre o projeto

Este projeto implementa uma aplicação web para consultar entregadores próximos a restaurantes em Belo Horizonte. O usuário pode selecionar um restaurante, definir um raio de busca e visualizar no mapa os entregadores encontrados, além de consultar as distâncias e os tempos estimados de deslocamento.

A solução utiliza Geohash para representar coordenadas geográficas em formato textual e uma Trie compacta para indexar essas representações e recuperar candidatos por prefixo. Em seguida, os candidatos são filtrados pela distância geográfica e, quando existe uma rota viável, têm suas distâncias e seus tempos de deslocamento estimados utilizando a rede de ruas.

O projeto também utiliza dados de restaurantes obtidos de uma base local e a rede viária do OpenStreetMap. Mecanismos de cache evitam repetir operações de obtenção de dados e geocodificação desnecessariamente.


## 2. Tecnologias utilizadas

| Tecnologia | Finalidade |
|---|---|
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
│   ├── gera_entregadores.py
│   └── interface.py
├── tests/
│   ├── teste_geohash.py
│   ├── teste_trie.py
│   └── benchmark_busca.py
├── bares.csv
├── bares_geocodificados.csv
├── app.py
├── requirements.txt
└── README.md

```

### Responsabilidade dos módulos

- ****`geohash.py`:**** implementa a codificação das coordenadas geográficas.
- ****`trie.py`:**** implementa a Trie compacta e suas operações.
- ****`busca_espaco.py`:**** constrói o índice espacial, identifica candidatos e realiza a filtragem geográfica.
- ****`gera_entregadores.py`:**** gera a frota sintética, carrega a rede viária e calcula estimativas de rotas.
- ****`interface.py`:**** implementa a aplicação web, os controles de consulta, o mapa e a apresentação dos resultados.
- ****`bares.csv`:**** contém a base de restaurantes utilizada na aplicação.
- ****`bares_geocodificados.csv`:**** armazena os resultados persistidos da geocodificação dos restaurantes.


## 4. Representação geográfica com Geohash

A função `geohash(coordenadas, precision=8)` converte uma latitude e longitude em uma cadeia de caracteres. A precisão define o comprimento do código: cada caractere representa 5 bits de informação espacial, alternando subdivisões dos intervalos de longitude e latitude. Quanto maior a precisão, menor é a célula representada.

A busca também utiliza `geohash_celula(linha, coluna, precision)`, que codifica uma célula a partir dos índices de linha e coluna. Isso permite enumerar as células que cobrem uma região de consulta, sem precisar gerar códigos para pontos aleatórios.

Na implementação atual, os entregadores são armazenados com Geohash de precisão 8, enquanto `PRECISAO_INDICE = 6` controla os prefixos usados na consulta. Portanto, cada prefixo consultado representa uma célula mais ampla e pode corresponder a vários Geohashes completos armazenados na Trie.

Para uma precisão `p`, existem `5 * p` bits. Eles são divididos entre longitude e latitude: `bits_lon = (total_bits + 1) // 2` e `bits_lat = total_bits // 2`. As dimensões angulares aproximadas da célula são `360 / 2**bits_lon` graus de longitude e `180 / 2**bits_lat` graus de latitude.

A busca espacial converte o raio em uma caixa aproximada de latitude e longitude. A margem de longitude considera a latitude por meio do cosseno, pois um grau de longitude representa distâncias diferentes conforme a latitude. A seleção das células inclui uma margem adicional de uma célula nas bordas, para evitar excluir candidatos que estejam próximos aos limites.

Células próximas podem ter prefixos diferentes se estiverem em lados opostos de uma fronteira. Por isso, a busca consulta todas as células cobertas pela caixa e depois aplica um filtro geométrico pela distância em linha reta. O Geohash serve para selecionar candidatos; não substitui esse filtro final.


## 5. Trie compacta

A Trie compacta indexa os códigos Geohash dos entregadores e permite recuperar valores associados a chaves que começam com determinado prefixo. No projeto, cada chave é um Geohash e os valores são IDs de entregadores.

### 5.1. Estrutura interna

Cada nó possui três campos:

- `label`: trecho da chave representado pelo nó. A raiz usa uma string vazia; os demais nós armazenam trechos não vazios.
- `children`: dicionário que associa o primeiro caractere do rótulo de cada filho ao próprio filho.
- `values`: conjunto dos valores associados à chave que termina exatamente naquele nó.

Como `values` é um conjunto, a mesma associação `(key, value)` não é armazenada duas vezes. Uma chave pode estar associada a vários valores, por exemplo quando mais de um entregador possui o mesmo Geohash. O atributo `size` conta pares únicos `(chave, valor)`, e não apenas a quantidade de chaves distintas.

| Operação | Descrição |
|---|---|
| `insert(key, value)` | Insere a associação entre chave e valor; retorna `True` somente se o par for novo. |
| `search_prefix(prefix)` | Recupera os valores associados às chaves que começam com o prefixo. |
| `search_prefixes(prefixes)` | Consulta vários prefixos e reúne os valores em um conjunto, removendo duplicatas. |
| `contains(key, value=None)` | Verifica se a chave existe; se `value` for informado como valor diferente de `None`, também verifica a associação. |
| `remove(key, value)` | Remove somente o par informado, se existir. |
| `clear()` | Substitui a raiz por uma nova raiz vazia e zera `size`. |

**Detalhe da interface:** `search_prefix()` retorna um conjunto quando encontra correspondências e uma lista vazia quando não encontra. Portanto, o tipo de retorno não é uniforme. `search_prefixes()` sempre retorna uma lista, construída a partir da união dos resultados em um conjunto.

### 5.2. Inserção e divisão de rótulos

A inserção compara a chave restante com o rótulo do filho que começa pelo mesmo caractere. Há três situações principais:

1. **Não existe filho compatível:** cria um novo nó cujo rótulo contém toda a parte restante da chave.
2. **O rótulo do filho corresponde por inteiro ao início da chave restante:** continua a inserção no filho, processando apenas os caracteres ainda não consumidos.
3. **A chave e o rótulo compartilham apenas um prefixo:** cria um nó intermediário com o prefixo comum, encurta o rótulo do filho existente e, se necessário, cria outro filho para o sufixo da nova chave. Se a nova chave terminar exatamente no prefixo comum, o valor é armazenado no nó intermediário.

A compactação mantém sequências de caracteres em um mesmo rótulo, em vez de criar um nó para cada caractere. O método `_insert()` é recursivo e processa os trechos restantes da chave. Uma inserção duplicada não altera o conjunto nem incrementa `size`.

### 5.3. Busca por prefixo

O método `search_prefix(prefix)` percorre os rótulos compactados até localizar a região que corresponde ao prefixo. Ele considera também o caso em que o prefixo termina no meio do rótulo de um filho: se o rótulo desse filho começa com todo o prefixo restante, todas as chaves abaixo dele são correspondências.

Se não houver correspondência, retorna `[]`. Se houver, chama `_collect()` para reunir os valores do nó encontrado e de todos os seus descendentes. A coleta usa uma pilha explícita e um laço iterativo, não chamadas recursivas. Os valores são reunidos em um conjunto, o que elimina duplicatas.

`search_prefixes(prefixes)` repete a consulta para cada prefixo e combina os resultados em um conjunto. Isso é útil na consulta espacial, em que os prefixos Geohash gerados podem recuperar o mesmo ID. A deduplicação evita processar repetidamente um mesmo identificador, mas não elimina o custo de gerar os prefixos, percorrer a estrutura, coletar os valores e recuperar os registros completos.

### 5.4. Verificação, remoção e compactação

`contains(key, value=None)` percorre os rótulos completos da chave. Quando `value` é omitido ou vale `None`, verifica se o nó terminal possui algum valor; caso contrário, verifica se o valor específico pertence ao conjunto. Por causa desse uso de `None` como sinalizador, o método não permite distinguir uma consulta pela presença explícita do valor `None`.

`remove(key, value)` remove apenas a associação solicitada e decrementa `size` se a remoção ocorrer. O método recursivo `_remove()` então reorganiza o caminho: elimina nós que ficaram sem valores e sem filhos, ou combina o rótulo de um nó sem valores com o rótulo de seu único filho. Essa reorganização mantém a estrutura compacta após remoções.

`clear()` cria uma nova raiz e define `size` como zero. Não percorre manualmente todos os nós; os objetos antigos ficam sujeitos à gestão de memória do Python quando deixam de ser referenciados.

### 5.5. Complexidade temporal

Considere `L` o comprimento da chave ou do prefixo, e `S` o custo de visitar a subárvore e reunir os valores correspondentes. Com acesso médio eficiente ao dicionário de filhos, as complexidades aproximadas são:

| Operação | Complexidade temporal aproximada |
|---|---|
| Inserção | `O(L)` para comparar os caracteres e percorrer o caminho; há custo adicional constante para criar ou dividir nós, sem contar o custo de hashing dos valores. |
| Busca por chave exata (`contains`) | `O(L)` em média. |
| Busca por prefixo (`search_prefix`) | `O(L + S)`, incluindo a coleta da subárvore correspondente. |
| Busca de vários prefixos (`search_prefixes`) | Soma dos custos das consultas individuais e da união dos valores coletados. |
| Remoção | `O(L)` para percorrer a chave e reorganizar o caminho, em média. |
| Limpeza (`clear`) | `O(1)` para substituir a raiz e zerar o contador; a recuperação da memória dos objetos antigos é gerenciada pelo Python. |

Essas estimativas não garantem que a Trie seja mais rápida do que uma varredura sequencial. Na aplicação, também importam a quantidade de prefixos consultados, o número de nós visitados, a quantidade de valores coletados e o custo de recuperar os registros no dicionário `por_id`.

### 5.6. Complexidade espacial

Se houver `K` chaves distintas, comprimento máximo `L` e `P` associações únicas entre chaves e valores, o armazenamento dos rótulos é limitado por `O(KL)` como estimativa geral, e os valores associados ocupam espaço proporcional a `P`. A compactação pode reduzir o número de nós em relação a uma Trie não compactada, sobretudo em caminhos sem ramificações; ela não elimina o armazenamento das chaves e das associações.

O índice espacial também mantém um dicionário `por_id` com os registros completos. Portanto, o consumo total de memória inclui a Trie, as associações chave–ID e o dicionário de registros.

### 5.7. Construção do índice espacial

A função `construir_indice(entregadores)` insere o Geohash de cada entregador na Trie, associando-o ao ID correspondente. Em paralelo, cria o dicionário `por_id`, que permite recuperar o registro completo a partir do ID.

O índice tem, portanto, duas partes:

- **Trie:** recupera IDs a partir de prefixos geográficos.
- **Dicionário `por_id`:** recupera os registros completos a partir dos IDs.

O índice pode ser construído uma vez e reutilizado em várias consultas. Por isso, o benchmark de consulta apresentado na seção 13 mede separadamente a busca com o índice já construído.



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

A função `gerar_entregadores(...)`, no módulo `gera_entregadores.py`, cria registros sintéticos de entregadores para a aplicação. A ideia é gerar posições próximas aos restaurantes, em vez de distribuir os pontos uniformemente por toda a cidade.

O processo consiste em:

1. recebe a lista de restaurantes e a quantidade de entregadores desejada;
2. sorteia posições próximas aos restaurantes, usando uma distribuição normal cuja dispersão é controlada por `sigma_km`;
3. associa as posições geradas à rede viária, usando o nó mais próximo quando essa etapa está habilitada na implementação;
4. armazena em cada registro um identificador, latitude, longitude e o Geohash calculado a partir das coordenadas finais.

O parâmetro `sigma_km` controla a dispersão da distribuição inicial: valores maiores tendem a gerar posições mais distantes do restaurante de referência. A posição final pode mudar ao ser associada à rede viária, pois passa a corresponder a um nó do grafo.

A geração da frota e a construção do índice são etapas distintas. A frota contém os registros; `construir_indice()` indexa os Geohashes desses registros e cria o mapa `por_id` para recuperar os dados completos durante a consulta. Para benchmarks reproduzíveis, deve-se fixar a semente do gerador aleatório, como faz o benchmark apresentado na seção 13.

## 8. Rede viária e estimativa de rotas



A função `carregar_grafo()` obtém a rede viária de Belo Horizonte por meio do OSMnx e prepara os atributos necessários para estimar o tempo de viagem.

São atribuídas velocidades de referência a diferentes categorias de vias para calcular o tempo esperado de entrega. Essas velocidades são aproximações e não incorporam condições de trânsito em tempo real.

### 8.1. Associação de coordenadas aos nós

A função `no_mais_proximo(lat, lon)` identifica o nó da rede viária mais próximo de uma coordenada geográfica. A implementação utiliza arrays NumPy com as coordenadas dos nós e percorre esses dados para determinar o mais próximo.

Esse método evita a necessidade de uma estrutura espacial adicional, mas seu custo cresce linearmente com o número de nós do grafo.

### 8.2. Cálculo de rotas

A função `estimar_rota(...)` associa as posições de origem e destino aos nós mais próximos e procura um caminho utilizando o atributo `travel_time`.

Quando há uma rota válida, são retornadas a distância estimada pela rede viária, em quilômetros, e o tempo estimado de deslocamento, em minutos. Quando não existe uma rota válida, o candidato pode ser descartado.

A distância pela rede viária não é necessariamente igual à distância em linha reta, pois depende das conexões, da topologia da rede e das restrições de circulação.

## 9. Algoritmo de busca espacial

O módulo `busca_espaco.py` separa a construção do índice, a seleção de células candidatas e a filtragem final.

### 9.1. `construir_indice(entregadores, precision=PRECISAO_INDICE)`

Percorre a frota e insere na Trie o Geohash de cada entregador associado ao seu identificador. Também cria o dicionário `por_id`, que mapeia cada ID ao registro completo, e guarda a precisão usada na consulta. Como a frota normalmente não muda entre consultas, o índice deve ser construído uma vez e reutilizado.

### 9.2. `buscar_prefixos_vizinhos(centro, raio_km, precision)`

Converte o raio em limites de latitude e longitude, calcula o tamanho das células para a precisão escolhida e enumera as linhas e colunas que cobrem a caixa de busca. A margem adicional nas bordas torna a seleção conservadora: pode recuperar candidatos a mais, mas o filtro final os remove se estiverem fora do raio.

### 9.3. `buscar_ids_candidatos(indice, prefixos)`

Consulta a Trie pelos prefixos e retorna os IDs encontrados. No benchmark atual, a consulta é feita para cada prefixo com `search_prefix()` e os resultados são unidos em um conjunto, para eliminar duplicatas.

### 9.4. `distancia_km(lat1, lon1, lat2, lon2)`

Estima a distância em linha reta usando uma aproximação local: converte diferenças de latitude para quilômetros e ajusta a diferença de longitude pela latitude. É uma aproximação apropriada para filtrar pontos próximos em Belo Horizonte, mas não é a distância percorrida pela rede viária.

### 9.5. `buscar_entregadores(frota, restaurante, raio_km, indice=None)`

A consulta completa segue estas etapas:

1. valida o raio e lê as coordenadas do restaurante;
2. se existe índice, gera os prefixos vizinhos, consulta a Trie e recupera os registros completos por `por_id`; caso contrário, examina a frota inteira;
3. calcula a distância em linha reta e descarta entregadores que estejam fora do raio;
4. para os candidatos restantes, chama `estimar_rota()` para calcular distância e tempo pela rede viária; candidatos sem rota válida são descartados;
5. ordena os resultados pelo ETA, do menor para o maior.

O filtro do raio é geográfico, enquanto a distância retornada por `estimar_rota()` é viária. Logo, a distância viária pode ser maior do que o raio sem que isso seja uma contradição. O raio determina quais posições são candidatas, e a rota estima o deslocamento pela rede de ruas.

O cálculo de rotas é significativamente mais custoso do que comparar coordenadas. Filtrar primeiro por distância em linha reta reduz o número de chamadas a `estimar_rota()`. Os benchmarks da seção 13 isolam a busca espacial e não incluem roteamento nem ETA, para comparar somente a seleção dos entregadores.

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


## 13. Avaliação experimental


Esta seção apresenta o benchmark da consulta espacial, realizado para comparar a Trie compacta com uma busca exaustiva sobre a frota.

### 13.1. Objetivo e metodologia

O objetivo foi verificar se a indexação por Geohash e Trie reduz o tempo necessário para identificar entregadores dentro de um raio de busca.

Foram comparadas duas estratégias:


- ****Consulta indexada:**** gera prefixos Geohash, consulta a Trie, reúne os identificadores candidatos e filtra os registros pela distância em linha reta.
- ****Busca exaustiva:**** percorre toda a frota e aplica o mesmo filtro de distância.

A frota sintética foi gerada com uma semente fixa (`seed=3`) e as consultas utilizaram o centro geográfico \\((-19.9191, -43.9386)\\), com raio de 2 km. Foram avaliados cinco tamanhos de frota, com dez repetições por estratégia.

O índice foi construído antes da medição e reutilizado nas consultas. O tempo de construção da Trie, o cálculo de rotas e a estimativa de ETA não foram incluídos.

O tempo informado corresponde à mediana das dez medições de cada estratégia. A comparação também verificou se ambas retornavam exatamente os mesmos identificadores.

### 13.2. Resultados

Os resultados obtidos foram:

| Quantidade de entregadores | Resultados equivalentes | Trie (ms) | Busca exaustiva (ms) | Speedup da Trie |
|---:|:---:|---:|---:|---:|
| 1.000 | Sim (88) | 0,493 | 0,247 | 0,50x |
| 5.000 | Sim (470) | 1,645 | 1,210 | 0,74x |
| 10.000 | Sim (964) | 3,464 | 2,476 | 0,71x |
| 20.000 | Sim (1.988) | 7,829 | 5,208 | 0,67x |
| 50.000 | Sim (5.008) | 23,599 | 13,360 | 0,57x |

**Correção dos resultados:** em todos os cinco cenários, a consulta indexada e a busca exaustiva retornaram conjuntos idênticos de entregadores.

A razão apresentada corresponde ao tempo da Trie dividido pelo tempo da busca exaustiva. Portanto, valores superiores a 1 indicam que a Trie foi mais lenta no cenário medido.

### 13.3. Interpretação dos resultados

Em todos os tamanhos de frota avaliados, a busca exaustiva apresentou menor tempo de execução. 

Na maior frota, a consulta indexada encontrou 5.008 entregadores dentro do raio de busca. Apesar de reduzir a quantidade de registros submetidos à filtragem final, a Trie precisa gerar os prefixos Geohash, percorrer a estrutura, reunir os identificadores, eliminar duplicatas e recuperar os registros correspondentes antes de calcular as distâncias.

A busca exaustiva, por outro lado, percorre sequencialmente a lista de entregadores e calcula a distância de cada registro. Essa operação tem um fluxo de execução simples e pouco overhead adicional, o que pode torná-la mais eficiente para os tamanhos de frota testados.

O speedup da Trie diminuiu de 0,50x, para 1.000 entregadores, para 0,57x, para 50.000. Isso indica que a diferença relativa de desempenho varia conforme o tamanho da entrada, mas a Trie permaneceu mais lenta em todos os cenários avaliados. Os resultados não permitem concluir que essa tendência continuará para frotas maiores.

### 13.3. Recursão e coleta dos resultados

Na implementação atual, a inserção (_insert) e a remoção (_remove) são recursivas. Já a coleta dos valores (_collect) utiliza uma pilha explícita e um laço iterativo, evitando chamadas recursivas durante a travessia dos descendentes.

Como o índice é construído antes da medição e o benchmark não executa remoções, o tempo medido não inclui o custo de _insert nem de _remove. Portanto, a recursão desses métodos não explica diretamente os tempos apresentados.

Durante a consulta, a Trie ainda precisa localizar cada prefixo e percorrer a subárvore correspondente para coletar os valores. O custo dessa coleta depende da quantidade de nós visitados e dos valores encontrados. O benchmark não separa o tempo gasto em cada etapa; assim, não é possível identificar apenas com esses resultados qual delas representa o maior custo.

### 13.5. Relação com o desempenho total da aplicação

Este experimento não inclui o cálculo de rotas. Isso é importante porque o cálculo de tempo de chegada pela rede viária pode dominar o tempo total de uma consulta completa.

A avaliação espacial isolada permite observar o custo da estrutura de dados sem que as operações de roteamento ocultem as diferenças. Entretanto, os resultados aqui apresentados não permitem concluir diretamente qual estratégia oferece o menor tempo de resposta para a aplicação inteira.

Uma avaliação completa deve considerar o tempo de seleção espacial, a quantidade de candidatos que precisam de roteamento e o custo de estimar suas rotas.

### 13.7. Conclusão do benchmark

Para os dados sintéticos, o centro geográfico, o raio e os tamanhos de frota utilizados, a busca exaustiva foi mais rápida do que a consulta com Trie compacta em todos os cenários. Ambas as estratégias produziram resultados equivalentes, mas a redução da quantidade de distâncias calculadas não compensou o custo adicional da indexação durante as consultas.

Isso não significa que uma Trie compacta seja sempre inadequada para consultas espaciais. O desempenho depende da implementação, da distribuição dos dados, da resolução do Geohash, da quantidade de prefixos consultados e do número de candidatos recuperados.

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

Os benchmarks demonstraram que, nos cenários testados, a Trie compacta recuperou os mesmos resultados da busca exaustiva, mas não apresentou vantagem temporal. A medição mais recente melhorou em relação à original, embora a consulta sequencial ainda tenha sido mais rápida.

Esse resultado destaca a importância de avaliar com testes as estruturas de dados, pois apesar da estrutura reduzir o conjunto de registros examinados, ainda assim pode ser mais lenta devido ao overhead de navegação e recuperação de resultados.

## 17. Referências

- OpenStreetMap. https\://www.openstreetmap.org/
- OSMnx. Documentação da biblioteca para obtenção, análise e roteamento em redes viárias. https\://osmnx.readthedocs.io/
- Nominatim. Documentação do serviço de geocodificação do OpenStreetMap. https\://nominatim.org/
- Dash. https\://dash.plotly.com/
- Dash Leaflet. https\://www.dash-leaflet.com/
- pytest. https\://docs.pytest.org/
