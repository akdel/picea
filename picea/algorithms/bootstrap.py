from picea.tree import Tree, treeplot
from typing import \
    Iterable, List, Dict, Tuple, Set
import numpy as np
from dataclasses import dataclass
from picea.algorithms import neighbor_joining as nj
from multiprocessing import Pool
from random import randint
from sklearn.cluster import AgglomerativeClustering as agg
from copy import deepcopy


@dataclass
class Clade:
    internode: Tree
    clade: Set[str]
    depth: int

    @classmethod
    def from_internode(cls, internode: Tree, banned: [None, Set[str]] = None) -> 'Clade':
        """
        Creates Clade from a given internode.
        :param internode: A node which is not a leaf.
        :param banned: banned node names.
        :return: Clade instance
        """
        assert internode.children is not None  # makes sure that it's not a leaf
        if banned is None:
            banned = set()
        clade: Set[str] = {x.name for x in internode.leaves if x.name not in banned}  # removes any banned leaves. this is used in bootstrapping.
        return cls(internode, clade, internode.depth)

    def compare_to(self, other: 'Clade') -> bool:
        """
        Compares the clade leaves to another.
        :param other: Clade instance to be compared
        :return: returns True if clades are equal.
        """
        if self.clade == other.clade:
            return True
        else:
            return False


@dataclass
class Clades:
    tree: Tree
    clades: List[Clade]
    bootstrap_scores: Dict[str, int]

    @classmethod
    def from_tree(cls, tree: Tree, banned: [None, Set[str]] = None) -> 'Clades':
        """
        Creates clades from a tree. Clades instance stores Clade instance per internode in the tree.
        :param tree:
        :param banned:
        :return: Clades
        """
        tree: Tree = tree.root
        queue: List[Tree] = [tree]
        clades: List[Clade] = list()
        while queue:
            node = queue.pop(0)
            if node.children is not None:
                clades.append(Clade.from_internode(node, banned))
            else:
                continue
            queue += node.children
        return cls(tree.root, clades, {x.name: 0 for x in tree.breadth_first() if x.children is not None})

    def redo_with_banned(self, banned: Set[str]) -> 'Clades':
        """
        Recreates the clades for the tree while keeping bootstrap scores.
        :param banned: New banned leaf names
        :return:
        """
        new_clades: Clades = Clades.from_tree(self.tree, banned)
        new_clades.bootstrap_scores = self.bootstrap_scores
        return new_clades

    def compare_to_other(self, other: 'Clades') -> None:
        """
        Compares Clades of a tree to another tree while scoring the internode if a clade attached exists in
         both of the trees.
        :param other: Clades of other tree
        :return:
        """
        for this_clade in self.clades:
            for other_clade in other.clades:
                if this_clade.clade == other_clade.clade:
                    self.bootstrap_scores[this_clade.internode.name] += 1
                    break
                else:
                    continue


def make_tree_parallel_nj(distance_matrix_and_names_tuple: Tuple[np.ndarray, np.ndarray]) -> Tree:
    """
    Nj tree is made from random sampling with replacement from the distance matrix.
    :param distance_matrix_and_names_tuple:
    :return:
    """
    np.random.seed(randint(0, 1000000))
    selected_ids = np.random.choice(np.arange(distance_matrix_and_names_tuple[1].shape[0]),
                                    size=distance_matrix_and_names_tuple[1].shape[0],
                                    replace=True)
    return build_nj_tree_from_distance_matrix(distance_matrix_and_names_tuple[0][selected_ids, :][:, selected_ids],
                                              list(distance_matrix_and_names_tuple[1][selected_ids])).root

def make_tree_parallel_agg(data_and_names_tuple: Tuple[np.ndarray, np.ndarray]) -> Tree:
    """
    Nj tree is made from random sampling with replacement from the distance matrix.
    :param distance_matrix_and_names_tuple:
    :return:
    """
    np.random.seed(randint(0, 1000000))
    selected_ids = np.random.choice(np.arange(data_and_names_tuple[1].shape[0]),
                                    size=data_and_names_tuple[1].shape[0],
                                    replace=True)
    hc = agg()
    hc.fit(data_and_names_tuple[0][selected_ids])
    return Tree.from_sklearn(hc, names=data_and_names_tuple[1][selected_ids])




def prepare_bootstrap_trees_nj(distance_matrix: np.ndarray,
                               names: [None, List[str]] = None,
                               iteration: int = 10,
                               n_threads: int = 4) -> Tuple[Tree, List[Tree]]:
    """
    Makes bootstrap trees in parallel from a provided distance matrix.

    :param distance_matrix: (n * n) matrix
    :param names: names in order of the matrix.
    :param iteration: number of trees to be generated
    :param n_threads: number of cpu processes to spawn
    :return:
    """
    if names is None:
        names = [str(x) for x in range(distance_matrix.shape[0])]
    tree: Tree = build_nj_tree_from_distance_matrix(distance_matrix, names)
    names = np.array(names)
    p: Pool = Pool(n_threads)
    other_trees: List[Tree] = list(p.map(make_tree_parallel_nj, [(distance_matrix, names) for _ in range(iteration)]))
    return tree.root, other_trees


def prepare_bootstrap_trees_agg(data_array: np.ndarray,
                                names: [None, List[str]] = None,
                                iteration: int = 10,
                                linkage: str = "ward") -> Tuple[Tree, List[Tree]]:
    if names is None:
        names = [str(x) for x in range(data_array.shape[0])]
    hc = agg()
    hc.fit(data_array)
    tree: Tree = Tree.from_sklearn(hc, names)
    names = np.array(names)
    other_trees: List[Tree] = [make_tree_parallel_agg((data_array, names)) for _ in range(iteration)]
    return tree.root, other_trees


def bootstrap(tree: Tree, bootstrap_trees: List[Tree]) -> None:
    """
    Bootstraps tree and modifies weights for each internode as the bootstrap values.
    :param tree:
    :param bootstrap_trees:
    :return: None, mutating function! changes Tree node weights into percentage bootstrap values.
    """
    tree_clades: Clades = Clades.from_tree(tree)
    leaf_names: Set[str] = {x.name for x in tree.leaves}
    other_tree_clades: Iterable[Clades] = (Clades.from_tree(x) for x in bootstrap_trees)
    for other_clades in other_tree_clades:
        banned_names = leaf_names - {x.name for x in other_clades.tree.leaves}
        tree_clades.redo_with_banned(banned_names).compare_to_other(other_clades)
    for clade in tree_clades.clades:
        clade.internode.weight = (tree_clades.bootstrap_scores[clade.internode.name]/len(bootstrap_trees)) * 100


def build_nj_tree_from_distance_matrix(distance_matrix: np.ndarray, names: List[str]) -> Tree:
    list_of_edges: List[Tuple[int, int]] = [x[::-1] for x in nj.neighbor_joining(distance_matrix)[0]]
    return Tree.from_edge_list(list_of_edges, {i: names[i] for i in range(distance_matrix.shape[0])})


def main():
    from sklearn.metrics import pairwise_distances
    import matplotlib.pyplot as plt
    data = np.random.random_sample(size=(10, 5))
    # distance_matrix = pairwise_distances(data, metric="euclidean")
    nj_tree, other_nj_trees = prepare_bootstrap_trees_agg(data, iteration=100)
    nj_tree.bootstrap(other_nj_trees)

    print("-"*10)
    print(nj_tree.root.weight)
    print(nj_tree.root)
    print("-" * 10)
    treeplot(nj_tree, internode_names=True)
    print([x.weight for x in nj_tree.root.breadth_first()])
    plt.show()


if __name__ == "__main__":
    main()