from src.trie import CompactTrie


def test_prefix_search_and_split_labels():
    trie = CompactTrie()
    trie.insert("abcdef", "a")
    trie.insert("abcxyz", "b")
    trie.insert("abc", "c")
    assert set(trie.search_prefix("abc")) == {"a", "b", "c"}
    assert trie.search_prefix("abcdef") == ["a"]
    assert trie.search_prefix("abq") == []


def test_duplicate_and_remove():
    trie = CompactTrie()
    assert trie.insert("abc", 1)
    assert not trie.insert("abc", 1)
    assert trie.insert("abc", 2)
    assert len(trie) == 2
    assert trie.remove("abc", 1)
    assert set(trie.search_prefix("abc")) == {2}
    assert not trie.remove("abc", 1)


def test_clear():
    trie = CompactTrie()
    trie.insert("abc", 1)
    trie.clear()
    assert len(trie) == 0
    assert trie.search_prefix("a") == []
