# Shared category-ordering helper for sankey figures.
#
# Orders biolink categories so members of the same category group (see
# eckg.colors.NODE_TO_GROUP) sit adjacent to each other — e.g. Gene next to
# Protein, SmallMolecule next to Drug — instead of being interleaved purely
# by count.

from eckg.colors import GROUPS, NODE_TO_GROUP

# Groups follow the canonical order in eckg.colors.GROUPS (not data-driven —
# e.g. Miscellaneous always sorts last, even if its total count is largest).
_GROUP_RANK = {g: i for i, (g, _) in enumerate(GROUPS)}


def group_sorted(categories: list, sort_counts: dict, node_to_group: dict = None) -> list:
    """
    Order `categories` so members of the same biolink category group are
    adjacent, with groups in the canonical GROUPS order. Categories within
    a group are ordered by `sort_counts`, descending.

    `node_to_group` overrides eckg.colors.NODE_TO_GROUP for this call only —
    pass a custom mapping to reclassify specific categories into a
    different group without touching the shared mapping.
    """
    mapping = NODE_TO_GROUP if node_to_group is None else node_to_group

    def key(c):
        g = mapping.get(c, "Miscellaneous")
        return (_GROUP_RANK.get(g, len(GROUPS)), -sort_counts.get(c, 0))

    return sorted(categories, key=key)


def group_gaps(categories: list, base_gap: float, buffer: float, node_to_group: dict = None) -> list:
    """
    Build a list of `len(categories) - 1` gaps to sit between consecutive
    bars in an already group_sorted() list: `base_gap` between two
    categories in the same group, `base_gap + buffer` at a group boundary.
    Use this to leave room for post-hoc group-section labels.
    """
    mapping = NODE_TO_GROUP if node_to_group is None else node_to_group
    gaps = []
    for a, b in zip(categories, categories[1:]):
        same_group = mapping.get(a, "Miscellaneous") == mapping.get(b, "Miscellaneous")
        gaps.append(base_gap if same_group else base_gap + buffer)
    return gaps
