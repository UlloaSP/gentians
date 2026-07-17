SELECTED_PREDICATE = "gentians_internal_selected"


def parse_coverage_symbol_masks(symbols) -> tuple[int, int]:
    pos_mask = 0
    neg_mask = 0
    for symbol in symbols:
        if len(symbol.arguments) != 1:
            continue
        value = symbol.arguments[0].number
        if symbol.name == "extended_p":
            pos_mask |= 1 << value
        elif symbol.name == "extended_n":
            neg_mask |= 1 << value
    return pos_mask, neg_mask


def parse_selected_rule_tuple(symbols) -> tuple[int, ...]:
    return tuple(
        sorted(
            symbol.arguments[0].number
            for symbol in symbols
            if symbol.name == SELECTED_PREDICATE and len(symbol.arguments) == 1
        )
    )
