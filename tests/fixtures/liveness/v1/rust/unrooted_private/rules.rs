struct _UnrootedRule;

impl Specification<bool> for _UnrootedRule {
    fn is_satisfied_by(&self, value: &bool) -> bool {
        *value
    }
}
