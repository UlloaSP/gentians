from .coverage_symbols import active_symbol


class ExternalActivation:
    name = "externals"

    @staticmethod
    def declaration(max_program_clauses: int, rule_count: int) -> str:
        if not rule_count or not max_program_clauses:
            return ""
        return (
            f"#external active(0..{max_program_clauses - 1},"
            f"0..{rule_count - 1})."
        )

    @staticmethod
    def activate(control, active_pairs, _max_program_clauses, _rule_ids):
        for slot, rule_id in active_pairs:
            control.assign_external(active_symbol(slot, rule_id), True)
        return []

    @staticmethod
    def deactivate(control, active_pairs) -> None:
        for slot, rule_id in active_pairs:
            control.assign_external(active_symbol(slot, rule_id), False)
