from .coverage_symbols import active_symbol


class AssumptionActivation:
    name = "assumptions"

    @staticmethod
    def declaration(max_program_clauses: int, rule_count: int) -> str:
        if not rule_count or not max_program_clauses:
            return ""
        return (
            f"{{active(0..{max_program_clauses - 1},"
            f"0..{rule_count - 1})}}."
        )

    @staticmethod
    def activate(_control, active_pairs, max_program_clauses, rule_ids):
        return [
            (active_symbol(slot, rule_id), (slot, rule_id) in active_pairs)
            for slot in range(max_program_clauses)
            for rule_id in rule_ids
        ]

    @staticmethod
    def deactivate(_control, _active_pairs) -> None:
        return None
