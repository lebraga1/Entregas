class CompactTrie:
    class _Node:
        def __init__(self, label=""):
            self.label = label
            self.children = {}
            self.values = set()

    def __init__(self):
        self.root = self._Node()
        self._size = 0

    def __len__(self):
        return self._size

    def insert(self, key, value):
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        if not key:
            raise ValueError("key must not be empty")

        def insert_recursive(node, remaining):
            if not remaining:
                if value in node.values:
                    return False
                node.values.add(value)
                return True

            child = node.children.get(remaining[0])

            if child is None:
                leaf = self._Node(remaining)
                leaf.values.add(value)
                node.children[remaining[0]] = leaf
                return True

            # Encontra o prefixo comum entre a chave e o rótulo do filho
            i = 0
            while (
                i < len(remaining)
                and i < len(child.label)
                and remaining[i] == child.label[i]
            ):
                i += 1

            if i == len(child.label):
                return insert_recursive(child, remaining[i:])

            # Divide o rótulo quando a nova chave diverge ou termina no meio dele
            middle = self._Node(child.label[:i])
            child.label = child.label[i:]
            middle.children[child.label[0]] = child
            node.children[middle.label[0]] = middle

            suffix = remaining[i:]

            if suffix:
                leaf = self._Node(suffix)
                leaf.values.add(value)
                middle.children[suffix[0]] = leaf
            else:
                middle.values.add(value)

            return True

        inserted = insert_recursive(self.root, key)
        if inserted:
            self._size += 1
        return inserted

    def search_prefix(self, prefix):
        if not isinstance(prefix, str):
            raise TypeError("prefix must be a string")

        def collect(node):
            # Reúne os valores do nó e de todos os seus descendentes
            result = list(node.values)
            for child in node.children.values():
                result.extend(collect(child))
            return result

        def search(node, remaining):
            if not remaining:
                return collect(node)

            child = node.children.get(remaining[0])
            if child is None:
                return []

            i = 0
            while (
                i < len(remaining)
                and i < len(child.label)
                and remaining[i] == child.label[i]
            ):
                i += 1

            if i < min(len(remaining), len(child.label)):
                return []

            # O prefixo pode terminar no meio de um rótulo compactado
            if i == len(remaining):
                return collect(child)

            return search(child, remaining[i:])

        return search(self.root, prefix)

    def contains(self, key, value=None):
        if not isinstance(key, str):
            raise TypeError("key must be a string")

        def find(node, remaining):
            if not remaining:
                return node

            child = node.children.get(remaining[0])
            if child is None or not remaining.startswith(child.label):
                return None

            return find(child, remaining[len(child.label):])

        node = find(self.root, key)
        if node is None:
            return False

        return bool(node.values) if value is None else value in node.values

    def remove(self, key, value):
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        if not key:
            return False

        def remove_recursive(node, remaining):
            if not remaining:
                if value not in node.values:
                    return False
                node.values.remove(value)
                return True

            child = node.children.get(remaining[0])
            if child is None or not remaining.startswith(child.label):
                return False

            removed = remove_recursive(
                child, remaining[len(child.label):]
            )

            if removed:
                if not child.values and not child.children:
                    # Remove nós que ficaram vazios
                    del node.children[child.label[0]]
                elif not child.values and len(child.children) == 1:
                    # Junta nós consecutivos para preservar a compactação
                    grandchild = next(iter(child.children.values()))
                    grandchild.label = child.label + grandchild.label
                    del node.children[child.label[0]]
                    node.children[grandchild.label[0]] = grandchild

            return removed

        removed = remove_recursive(self.root, key)
        if removed:
            self._size -= 1
        return removed

    def clear(self):
        self.root = self._Node()
        self._size = 0