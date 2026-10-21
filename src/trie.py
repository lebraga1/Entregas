class CompactTrie:
    class Node:
        def __init__(self, label=""):
            # Cada nó guarda um trecho da chave, seus filhos e os valores associados
            self.label = label
            self.children = {}
            self.values = set()

    def __init__(self):
        # A raiz não representa nenhum caractere específico
        self.root = self.Node()
        # Quantidade de pares únicos (chave, valor) armazenados
        self.size = 0

    def __len__(self):
        return self.size

    def insert(self, key, value):
        # As chaves precisam ser strings não vazias
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        if not key:
            raise ValueError("key must not be empty")

        # A inserção retorna True somente quando adiciona um novo par
        inserted = self._insert(self.root, key, value)
        if inserted:
            self.size += 1
        return inserted

    def _insert(self, node, key, value):
        # Quando a chave termina, armazena o valor no nó atual
        if not key:
            if value in node.values:
                return False
            node.values.add(value)
            return True

        # Procura um filho que comece com o primeiro caractere da chave
        child = node.children.get(key[0])

        # Se não existir, cria um único nó para o restante da chave
        if child is None:
            leaf = self.Node(key)
            leaf.values.add(value)
            node.children[key[0]] = leaf
            return True

        # Descobre quantos caracteres são compartilhados entre os trechos
        i = 0
        while i < len(key) and i < len(child.label):
            if key[i] != child.label[i]:
                break
            i += 1

        # Se todo o trecho do filho coincide, continua a inserção nele
        if i == len(child.label):
            return self._insert(child, key[i:], value)

        # Divide o trecho quando as chaves compartilham apenas um prefixo
        # Isso mantém a Trie compacta, evitando um nó para cada caractere
        middle = self.Node(child.label[:i])
        child.label = child.label[i:]
        middle.children[child.label[0]] = child
        node.children[middle.label[0]] = middle

        # Se ainda restarem caracteres, cria um novo ramo
        suffix = key[i:]
        if suffix:
            leaf = self.Node(suffix)
            leaf.values.add(value)
            middle.children[suffix[0]] = leaf
        else:
            # A nova chave termina exatamente no nó intermediário
            middle.values.add(value)

        return True

    def search_prefix(self, prefix):
        # Percorre os trechos comprimidos até encontrar o prefixo
        if not isinstance(prefix, str):
            raise TypeError("prefix must be a string")

        node = self.root
        remaining = prefix

        while remaining:
            child = node.children.get(remaining[0])
            if child is None:
                return []

            # O prefixo pode terminar no meio de um trecho comprimido
            # Nesse caso, todas as chaves abaixo desse nó são correspondências
            if child.label.startswith(remaining):
                return self._collect(child)

            # Se os trechos não coincidirem completamente, não há correspondência
            if not remaining.startswith(child.label):
                return []

            remaining = remaining[len(child.label):]
            node = child

        return self._collect(node)

    def search_prefixes(self, prefixes):
        # Une os resultados para evitar valores repetidos entre prefixos
        result = set()
        for prefix in prefixes:
            result.update(self.search_prefix(prefix))
        return list(result)

    def _collect(self, node):
        # Percorre a subárvore para reunir todos os valores encontrados
        # Uma pilha evita depender da profundidade da recursão para aumentar eficiência
        result = set()
        stack = [node]

        while stack:
            current = stack.pop()
            result.update(current.values)

            for child in current.children.values():
                stack.append(child)

        return result

    def contains(self, key, value=None):
        # Verifica se a chave existe e, opcionalmente, se contém um valor
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        node = self.root
        remaining = key

        while remaining:
            child = node.children.get(remaining[0])
            if child is None:
                return False

            # A chave precisa corresponder ao trecho inteiro do filho
            if not remaining.startswith(child.label):
                return False

            remaining = remaining[len(child.label):]
            node = child

        if value is None:
            return bool(node.values)

        return value in node.values

    def remove(self, key, value):
        # Remove apenas o par informado, sem apagar outros valores da chave
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        if not key:
            return False

        removed = self._remove(self.root, key, value)
        if removed:
            self.size -= 1

        return removed

    def _remove(self, node, key, value):
        # Ao chegar ao final da chave, remove o valor se ele existir
        if not key:
            if value not in node.values:
                return False

            node.values.remove(value)
            return True

        child = node.children.get(key[0])
        if child is None or not key.startswith(child.label):
            return False

        # Continua a busca no filho
        removed = self._remove(child, key[len(child.label):], value)
        if not removed:
            return False

        # Elimina nós vazios para não manter caminhos desnecessários
        if not child.values and not child.children:
            del node.children[child.label[0]]

        # Se restar apenas um filho, junta os trechos para manter a Trie compacta
        elif not child.values and len(child.children) == 1:
            grandchild = next(iter(child.children.values()))
            old_label = child.label
            grandchild.label = old_label + grandchild.label

            del node.children[old_label[0]]
            node.children[grandchild.label[0]] = grandchild

        return True

    def clear(self):
        # Reinicia a estrutura e zera a quantidade de pares armazenados
        self.root = self.Node()
        self.size = 0