# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.ou_import.tree_model` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.ou_import import tree_model


#
# test tree Node
#


@pytest.fixture
def node():
    return tree_model.Node(
        "internal-id:2",
        parent_id="internal-id:1",
        node_data={'foo': "bar"},
    )


def test_node_init(node):
    assert node.node_id == "internal-id:2"
    assert node.parent_id == "internal-id:1"
    assert node.node_data == {'foo': "bar"}
    assert node.parent is None
    assert node.children == tuple()
    assert node.path == tuple()


def test_node_repr(node):
    repr_text = repr(node)
    assert "Node" in repr_text
    assert "node_id=" in repr_text
    assert "parent_id=" in repr_text
    assert "internal-id:2" in repr_text
    assert "internal-id:1" in repr_text


@pytest.fixture
def root():
    return tree_model.Node("internal-id:1")


def test_set_parent(node, root):
    node.parent = root
    assert node.parent is root


def test_del_parent(node, root):
    node.parent = root
    del node.parent
    assert node.parent is None


def test_set_parent_self(node):
    with pytest.raises(AttributeError) as exc_info:
        node.parent = node

    error = six.text_type(exc_info.value)
    assert error == "cannot set self as parent"


def test_set_parent_cycle(node, root):
    node.parent = root
    with pytest.raises(AttributeError) as exc_info:
        root.parent = node

    error = six.text_type(exc_info.value)
    assert error.startswith("cycle detected in node")


@pytest.fixture
def children(node, root):
    node.parent = root
    child_1 = tree_model.Node("internal-id:3", parent_id="internal-id:2")
    child_2 = tree_model.Node("internal-id:4", parent_id="internal-id:2")
    child_3 = tree_model.Node("internal-id:5", parent_id="internal-id:2")
    child_1.parent = node
    child_2.parent = node
    child_3.parent = node
    return [child_1, child_2, child_3]


def test_get_children(node, children):
    assert set(node.children) == set(children)


def test_get_path(root, node, children):
    child = children[0]
    assert child.path == (node, root)


def test_build_trees():
    root_1 = tree_model.Node("internal-id:1")
    node_1 = tree_model.Node("internal-id:2", parent_id="internal-id:1")
    child_1 = tree_model.Node("internal-id:3", parent_id="internal-id:2")

    # a second, intentional tree
    root_2 = tree_model.Node("internal-id:6")
    node_2 = tree_model.Node("internal-id:7", parent_id="internal-id:6")

    # a third, accidental root, refers to a missing node
    root_3 = tree_model.Node("internal-id:9", parent_id="missing-id:8")

    nodes = [root_1, node_1, child_1, root_2, node_2, root_3]
    roots = tree_model.build_trees(nodes)
    assert len(roots) == 3
    assert set(roots) == set((root_1, root_2, root_3))
    assert child_1.path == (node_1, root_1)
