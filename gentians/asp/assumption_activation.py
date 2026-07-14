from .coverage_symbols import ACTIVE_PREDICATE, active_symbol


class AssumptionActivation:
    name = "assumptions"

    @staticmethod
    def declaration(rule_count: int) -> str:
        if not rule_count:
            return ""
        return f"{{{ACTIVE_PREDICATE}(0..{rule_count - 1})}}."

    @staticmethod
    def activate(_control, active_rule_ids, rule_ids):
        return [
            (active_symbol(rule_id), rule_id in active_rule_ids)
            for rule_id in rule_ids
        ]

    @staticmethod
    def deactivate(_control, _active_rule_ids) -> None:
        return None
