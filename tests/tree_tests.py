from unittest import TestCase

from picea import Tree


class SequenceTests(TestCase):
    def setUp(self):
        self.newick = '(((a,b),(c,d)),e);'

    def test_empty_init(self):
        Tree()

    def test_parsing(self):
        Tree.from_newick(self.newick)

    def test_input_output(self):
        tree = Tree.from_newick(self.newick)
        assert self.newick == tree.to_newick(branch_lengths=False)

    def test_root(self):
        tree = Tree.from_newick(self.newick)
        deep_node = tree.loc['a']
        assert deep_node.root == tree
