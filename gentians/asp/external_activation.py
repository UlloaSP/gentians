from .coverage_symbols import ACTIVE_PREDICATE, active_symbol


class ExternalActivation:
    name = "externals"

    @staticmethod
    def declaration(rule_count: int) -> str:
        if not rule_count:
            return ""
        return f"#external {ACTIVE_PREDICATE}(0..{rule_count - 1})."

    @staticmethod
    def activate(control, active_rule_ids, _rule_ids):
        for rule_id in active_rule_ids:
            control.assign_external(active_symbol(rule_id), True)
        return []

    @staticmethod
    def deactivate(control, active_rule_ids) -> None:
        for rule_id in active_rule_ids:
            control.assign_external(active_symbol(rule_id), False)
